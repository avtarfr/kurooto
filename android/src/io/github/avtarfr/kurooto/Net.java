package io.github.avtarfr.kurooto;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Tiny HTTP helpers (no libraries). Call off the main thread. */
final class Net {
    static final class Reply {
        final int code;
        final String body;
        Reply(int code, String body) { this.code = code; this.body = body; }
        boolean ok() { return code >= 200 && code < 300; }
    }

    private Net() { }

    static byte[] readAll(InputStream in) throws java.io.IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        return out.toByteArray();
    }

    /** method GET or POST; key goes in x-call-secret; body may be null. Never throws: code -1 on network errors. */
    static Reply request(String method, String url, byte[] body, String contentType, String key, int readTimeoutMs) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod(method);
            c.setConnectTimeout(15000);
            c.setReadTimeout(readTimeoutMs);
            if (key != null && !key.isEmpty()) c.setRequestProperty("x-call-secret", key);
            if (body != null) {
                c.setDoOutput(true);
                c.setFixedLengthStreamingMode(body.length);
                if (contentType != null) c.setRequestProperty("Content-Type", contentType);
                OutputStream o = c.getOutputStream();
                try { o.write(body); } finally { o.close(); }
            }
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            String text = "";
            if (in != null) {
                try { text = new String(readAll(in), Crypto.UTF8); } finally { in.close(); }
            }
            return new Reply(code, text);
        } catch (Exception e) {
            return new Reply(-1, "");
        } finally {
            if (c != null) c.disconnect();
        }
    }

    static Reply postJson(String url, String json, String key) {
        return request("POST", url, json.getBytes(Crypto.UTF8), "application/json", key, 30000);
    }
}
