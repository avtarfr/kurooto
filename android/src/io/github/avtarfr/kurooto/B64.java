package io.github.avtarfr.kurooto;

import java.io.ByteArrayOutputStream;

/** Base64 for every Android version and for plain-JVM tests (java.util.Base64 needs Android 8, android.util.Base64
 *  isn't on a desktop JVM). Decoding accepts both alphabets, with or without padding. */
final class B64 {
    private static final String STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    private static final String URL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

    private B64() { }

    static String encode(byte[] b, boolean url) {
        String abc = url ? URL : STD;
        StringBuilder sb = new StringBuilder((b.length + 2) / 3 * 4);
        for (int i = 0; i < b.length; i += 3) {
            int n = (b[i] & 0xff) << 16 | (i + 1 < b.length ? (b[i + 1] & 0xff) << 8 : 0) | (i + 2 < b.length ? b[i + 2] & 0xff : 0);
            sb.append(abc.charAt(n >> 18 & 63)).append(abc.charAt(n >> 12 & 63));
            if (i + 1 < b.length) sb.append(abc.charAt(n >> 6 & 63)); else if (!url) sb.append('=');
            if (i + 2 < b.length) sb.append(abc.charAt(n & 63)); else if (!url) sb.append('=');
        }
        return sb.toString();
    }

    static byte[] decode(String s) {
        ByteArrayOutputStream out = new ByteArrayOutputStream(s.length() * 3 / 4);
        int buf = 0, bits = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            int v;
            if (c >= 'A' && c <= 'Z') v = c - 'A';
            else if (c >= 'a' && c <= 'z') v = c - 'a' + 26;
            else if (c >= '0' && c <= '9') v = c - '0' + 52;
            else if (c == '+' || c == '-') v = 62;
            else if (c == '/' || c == '_') v = 63;
            else if (c == '=' || Character.isWhitespace(c)) continue;
            else throw new IllegalArgumentException("not base64");
            buf = buf << 6 | v;
            bits += 6;
            if (bits >= 8) {
                bits -= 8;
                out.write(buf >> bits & 0xff);
            }
        }
        return out.toByteArray();
    }
}
