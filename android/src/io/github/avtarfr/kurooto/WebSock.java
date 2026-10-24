package io.github.avtarfr.kurooto;

import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Map;

/** A small WebSocket client (RFC 6455) for the app's own connection to the call line (Direct, 0.7.0), with nothing
 *  but java.net: Android 6 has no WebSocket of its own and the app uses no libraries. Text messages only (what the
 *  line sends); pings are answered, a close ends it. Plain Java, so the JVM tests (LinkTest) run it against a local
 *  server. One reader thread; sending is safe from any thread. */
final class WebSock {
    static final String GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
    static final int MAX = 1 << 20; // a message this big is not from your call line (its own are a few KB)
    static final int TEXT = 1, CLOSE = 8, PING = 9, PONG = 10;
    static final java.nio.charset.Charset UTF8 = java.nio.charset.Charset.forName("UTF-8");

    /** The line said no (an HTTP status instead of 101): 404 an older line without it, 401/403 not paired. */
    static final class Refused extends IOException {
        final int code;
        Refused(int code) { super("refused: " + code); this.code = code; }
    }

    private final Socket sock;
    private final InputStream in;
    private final OutputStream out;
    private final SecureRandom rnd = new SecureRandom();

    private WebSock(Socket sock) throws IOException {
        this.sock = sock;
        this.in = sock.getInputStream();
        this.out = sock.getOutputStream();
    }

    /** The opening handshake on a socket that's already connected (TLS done, for https). */
    static WebSock open(Socket s, String host, String path, Map<String, String> headers) throws IOException {
        WebSock w = new WebSock(s);
        byte[] nonce = new byte[16];
        w.rnd.nextBytes(nonce);
        String key = B64.encode(nonce, false);
        StringBuilder req = new StringBuilder("GET ").append(path).append(" HTTP/1.1\r\nHost: ").append(host)
                .append("\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: ").append(key)
                .append("\r\nSec-WebSocket-Version: 13\r\nUser-Agent: kurooto-android\r\n");
        if (headers != null) for (Map.Entry<String, String> h : headers.entrySet()) req.append(h.getKey()).append(": ").append(h.getValue()).append("\r\n");
        req.append("\r\n");
        w.out.write(req.toString().getBytes(UTF8));
        w.out.flush();
        String status = w.line();
        String[] p = status.split(" ");
        int code = p.length > 1 ? parse(p[1]) : 0;
        String accept = "";
        for (String h; !(h = w.line()).isEmpty(); ) {
            int i = h.indexOf(':');
            if (i > 0 && h.substring(0, i).trim().equalsIgnoreCase("sec-websocket-accept")) accept = h.substring(i + 1).trim();
        }
        if (code != 101) { w.close(); throw new Refused(code); }
        if (!accept.equals(acceptKey(key))) { w.close(); throw new IOException("not a WebSocket answer"); }
        return w;
    }

    private static int parse(String s) {
        try { return Integer.parseInt(s.trim()); } catch (Exception e) { return 0; }
    }

    /** Sec-WebSocket-Accept for a Sec-WebSocket-Key. */
    static String acceptKey(String key) {
        try {
            return B64.encode(MessageDigest.getInstance("SHA-1").digest((key + GUID).getBytes(UTF8)), false);
        } catch (Exception e) {
            return "";
        }
    }

    private String line() throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        for (int c; (c = in.read()) != '\n'; ) {
            if (c < 0) throw new EOFException();
            if (c != '\r') b.write(c);
            if (b.size() > 8192) throw new IOException("header too long");
        }
        return new String(b.toByteArray(), UTF8);
    }

    private int byteOf() throws IOException {
        int c = in.read();
        if (c < 0) throw new EOFException();
        return c;
    }

    private byte[] bytes(long n) throws IOException {
        if (n > MAX) throw new IOException("message too big");
        byte[] b = new byte[(int) n];
        for (int at = 0; at < b.length; ) {
            int got = in.read(b, at, b.length - at);
            if (got < 0) throw new EOFException();
            at += got;
        }
        return b;
    }

    /** The next text message; "" for a ping or pong (something was heard). Throws at a close or a broken stream.
     *  Only the wait for a new message may time out (the socket's read timeout comes out as SocketTimeoutException
     *  and the stream is still good); one that stalls halfway breaks the stream, so it's an IOException then. */
    String read() throws IOException {
        ByteArrayOutputStream msg = new ByteArrayOutputStream();
        int b0 = byteOf();
        try {
            while (true) {
                String got = frameAfter(b0, msg);
                if (got != null) return got;
                b0 = byteOf(); // the next fragment
            }
        } catch (java.net.SocketTimeoutException e) {
            throw new IOException("the line stalled in the middle of a message");
        }
    }

    private boolean binary;

    /** The rest of a frame whose first byte is b0: a whole message (text; "" for binary), "" for a ping or pong
     *  between messages, or null when more fragments follow (kept in msg). */
    private String frameAfter(int b0, ByteArrayOutputStream msg) throws IOException {
        int b1 = byteOf();
        boolean fin = (b0 & 0x80) != 0, masked = (b1 & 0x80) != 0;
        int op = b0 & 0x0f;
        long n = b1 & 0x7f;
        if (n == 126) n = (byteOf() << 8) | byteOf();
        else if (n == 127) { n = 0; for (int i = 0; i < 8; i++) n = (n << 8) | byteOf(); }
        byte[] mask = masked ? bytes(4) : null;
        byte[] data = bytes(n);
        if (mask != null) for (int i = 0; i < data.length; i++) data[i] ^= mask[i & 3];
        if (op == PING) { send(PONG, data); return msg.size() == 0 ? "" : null; }
        if (op == PONG) return msg.size() == 0 ? "" : null;
        if (op == CLOSE) { try { send(CLOSE, new byte[0]); } catch (IOException ignored) { } close(); throw new EOFException("closed"); }
        if (op == TEXT || op == 2 || op == 0) {
            if (op != 0) binary = op == 2;
            msg.write(data, 0, data.length);
            if (msg.size() > MAX) throw new IOException("message too big");
            if (fin) return binary ? "" : new String(msg.toByteArray(), UTF8);
        }
        return null;
    }

    void sendText(String s) throws IOException { send(TEXT, s.getBytes(UTF8)); }

    /** One frame from this client: always masked, as the protocol asks. */
    synchronized void send(int op, byte[] data) throws IOException {
        byte[] mask = new byte[4];
        rnd.nextBytes(mask);
        out.write(frame(op, data, mask));
        out.flush();
    }

    static byte[] frame(int op, byte[] data, byte[] mask) {
        ByteArrayOutputStream f = new ByteArrayOutputStream(data.length + 14);
        f.write(0x80 | op);
        int m = mask == null ? 0 : 0x80;
        if (data.length < 126) f.write(m | data.length);
        else if (data.length < 65536) { f.write(m | 126); f.write(data.length >> 8); f.write(data.length & 0xff); }
        else { f.write(m | 127); for (int i = 7; i >= 0; i--) f.write(i >= 4 ? 0 : (int) ((long) data.length >> (8 * i)) & 0xff); }
        if (mask != null) f.write(mask, 0, 4);
        for (int i = 0; i < data.length; i++) f.write(mask == null ? data[i] : data[i] ^ mask[i & 3]);
        return f.toByteArray();
    }

    void timeout(int ms) {
        try { sock.setSoTimeout(ms); } catch (Exception ignored) { }
    }

    void close() {
        try { sock.close(); } catch (Exception ignored) { }
    }
}
