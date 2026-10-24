package io.github.avtarfr.kurooto;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicReference;

/** The app's own connection to the call line (0.7.0) on the JVM: where it goes, the wait between tries, second copies
 *  dropped (LinkRules), and the WebSocket client (WebSock) against a small server on this machine: the handshake
 *  with the device key, text, a fragmented message, the server's ping answered, the client's frames masked, a close,
 *  and an older line's 404. */
public class LinkTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok  " : "FAIL ") + what);
        if (!ok) failed++;
    }

    public static void main(String[] args) throws Exception {
        String[] t = LinkRules.target("https://line.example.org", 41);
        check(t != null && t[0].equals("line.example.org") && t[1].equals("443") && t[2].equals("/phone?after=41")
                && t[3].equals("tls"), "a line's address: TLS on 443, the last message number");
        String[] local = LinkRules.target("http://127.0.0.1:8787", -3);
        check(local != null && local[1].equals("8787") && local[2].equals("/phone?after=0") && local[3].isEmpty(), "a local test line");
        check(LinkRules.target("not a url", 0) == null && LinkRules.target("ftp://x.y", 0) == null, "not an address");

        check(LinkRules.backoffMs(0, 0) == 2000 && LinkRules.backoffMs(1, 0) == 4000 && LinkRules.backoffMs(9, 0) == 60_000,
                "2 s doubling to 60 s");
        check(LinkRules.backoffMs(0, 0.999) > 2600 && LinkRules.backoffMs(0, 0.999) <= 2667 && LinkRules.backoffMs(9, 0.5) == 70_000,
                "up to a third more, at random");

        String s = LinkRules.seen("", "aa", 3);
        check("aa".equals(s), "a first id is kept");
        check(LinkRules.seen(s, "aa", 3) == null, "a second copy is dropped");
        s = LinkRules.seen(LinkRules.seen(LinkRules.seen(s, "bb", 3), "cc", 3), "dd", 3);
        check("bb,cc,dd".equals(s), "only the newest are kept");
        check(LinkRules.seen(s, "aa", 3) != null, "an id long gone counts as new");
        check("bb,cc,dd".equals(LinkRules.seen(s, "", 3)), "no id (an older line): never a copy");
        check(LinkRules.seen("abc", "ab", 3) != null, "a prefix of another id isn't it");

        check(WebSock.acceptKey("dGhlIHNhbXBsZSBub25jZQ==").equals("s3pPLMBiTxaQ9kYGzzhZRbK+xOo="), "the accept key (RFC 6455's example)");
        byte[] f = WebSock.frame(WebSock.TEXT, "Hi".getBytes("UTF-8"), new byte[]{1, 2, 3, 4});
        check(f.length == 8 && (f[0] & 0xff) == 0x81 && (f[1] & 0xff) == 0x82 && (f[6] ^ 1) == 'H' && (f[7] ^ 2) == 'i', "a masked text frame");
        check(WebSock.frame(WebSock.TEXT, new byte[300], null)[1] == 126 && WebSock.frame(WebSock.TEXT, new byte[70000], null)[1] == 127,
                "longer lengths");

        session();
        refused();
        if (failed > 0) System.exit(1);
        System.out.println("LinkTest: all good");
    }

    /** What the call line's side does, by hand. */
    static void session() throws Exception {
        final ServerSocket server = new ServerSocket(0);
        final AtomicReference<String> heard = new AtomicReference<>(""), key = new AtomicReference<>("");
        Thread srv = new Thread(() -> {
            try (Socket s = server.accept()) {
                BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(), "UTF-8"));
                String line, wsKey = "";
                StringBuilder head = new StringBuilder();
                while (!(line = r.readLine()).isEmpty()) {
                    head.append(line).append('\n');
                    if (line.toLowerCase().startsWith("sec-websocket-key:")) wsKey = line.substring(18).trim();
                    if (line.toLowerCase().startsWith("x-call-secret:")) key.set(line.substring(14).trim());
                }
                heard.set(head.toString());
                OutputStream o = s.getOutputStream();
                o.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "
                        + WebSock.acceptKey(wsKey) + "\r\n\r\n").getBytes("UTF-8"));
                o.write(WebSock.frame(WebSock.TEXT, "{\"type\":\"hello\",\"seq\":3}".getBytes("UTF-8"), null));
                o.write(WebSock.frame(WebSock.PING, "p".getBytes("UTF-8"), null));
                byte[] a = WebSock.frame(WebSock.TEXT, "{\"seq\":4,".getBytes("UTF-8"), null);
                a[0] = 0x01; // not the last fragment
                o.write(a);
                byte[] b = WebSock.frame(0, "\"k1\":\"k1.x\"}".getBytes("UTF-8"), null);
                o.write(b);
                o.flush();
                InputStream in = s.getInputStream();
                // the pong for our ping, then the client's "ping": both masked
                int[] pong = frame(in);
                int[] ping = frame(in);
                check(pong[0] == WebSock.PONG && pong[1] == 1 && pong[2] == 1, "the server's ping is answered, masked");
                check(ping[0] == WebSock.TEXT && ping[1] == 1 && ping[2] == 4, "the client's \"ping\", masked");
                o.write(WebSock.frame(WebSock.TEXT, "pong".getBytes("UTF-8"), null));
                o.write(WebSock.frame(WebSock.CLOSE, new byte[0], null));
                o.flush();
                frame(in); // its close
            } catch (Exception e) {
                check(false, "the test server: " + e);
            }
        });
        srv.start();
        Socket c = new Socket("127.0.0.1", server.getLocalPort());
        c.setSoTimeout(5000);
        WebSock w = WebSock.open(c, "127.0.0.1:" + server.getLocalPort(), "/phone?after=2",
                Collections.singletonMap("x-call-secret", "d1.0123abcd." + repeat("ab", 32)));
        check(heard.get().startsWith("GET /phone?after=2 HTTP/1.1") && heard.get().contains("Upgrade: websocket"), "the upgrade request");
        check(key.get().startsWith("d1.0123abcd."), "with this phone's key");
        check(w.read().equals("{\"type\":\"hello\",\"seq\":3}"), "the hello");
        check(w.read().isEmpty(), "a ping is heard as something");
        check(w.read().equals("{\"seq\":4,\"k1\":\"k1.x\"}"), "a message in two fragments");
        w.sendText("ping");
        check(w.read().equals("pong"), "the line's \"pong\"");
        boolean closed = false;
        try { w.read(); } catch (java.io.EOFException e) { closed = true; }
        check(closed, "a close ends it");
        srv.join(5000);
        server.close();
    }

    static void refused() throws Exception {
        final ServerSocket server = new ServerSocket(0);
        Thread srv = new Thread(() -> {
            try (Socket s = server.accept()) {
                BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(), "UTF-8"));
                while (!r.readLine().isEmpty()) { /* the request */ }
                s.getOutputStream().write("HTTP/1.1 404 Not Found\r\ncontent-length: 2\r\n\r\n{}".getBytes("UTF-8"));
            } catch (Exception ignored) { }
        });
        srv.start();
        int code = 0;
        try {
            WebSock.open(new Socket("127.0.0.1", server.getLocalPort()), "x", "/phone?after=0", null);
        } catch (WebSock.Refused e) {
            code = e.code;
        }
        check(code == 404, "an older line (404): refused, with its status");
        srv.join(5000);
        server.close();
    }

    /** {opcode, masked 0/1, payload length} of the next frame from the client. */
    static int[] frame(InputStream in) throws Exception {
        int b0 = in.read(), b1 = in.read();
        int n = b1 & 0x7f;
        boolean masked = (b1 & 0x80) != 0;
        ByteArrayOutputStream skip = new ByteArrayOutputStream();
        for (int i = 0; i < (masked ? 4 : 0) + n; i++) skip.write(in.read());
        return new int[]{b0 & 0x0f, masked ? 1 : 0, n};
    }

    static String repeat(String s, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(s);
        return b.toString();
    }
}
