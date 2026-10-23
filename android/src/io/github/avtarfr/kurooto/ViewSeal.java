package io.github.avtarfr.kurooto;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.spec.ECParameterSpec;
import java.util.Arrays;
import java.util.zip.GZIPInputStream;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * "v1": Systems or the Notes map, as your computer sealed it for this phone (0.7.0; calls/line.py pack_v1, head_v1).
 * The snapshot is gzipped and sealed once with a fresh AES-256-GCM key (the blob: nonce || ciphertext+tag); the head
 * "v1 <kind> <rev> <key, base64url> <sha256 of the blob, hex>" is sealed for this phone alone (Seal, s1). Your call
 * line keeps both and can open neither. No Android classes here, so android/build.sh --test runs it on a plain JVM
 * (ViewsTest, against tests/fixtures/call-vectors.json).
 */
final class ViewSeal {
    static final long MAX_TEXT = 16L * 1024 * 1024; // a snapshot unpacks to at most this (the computer sends far less)

    static final class Opened {
        final String kind, text;
        final long rev;
        Opened(String kind, long rev, String text) { this.kind = kind; this.rev = rev; this.text = text; }
    }

    private ViewSeal() { }

    /** The snapshot, or null if it isn't sealed for this phone, isn't the blob its head names, or was changed. */
    static Opened open(PrivateKey mine, ECParameterSpec params, String head, byte[] blob) {
        String plain = Seal.open(mine, params, head);
        if (plain == null || blob == null || blob.length < 28) return null;
        String[] p = plain.split(" ");
        if (p.length != 5 || !"v1".equals(p[0]) || !p[2].matches("[0-9]{1,19}")) return null;
        try {
            if (!MessageDigest.isEqual(hex(MessageDigest.getInstance("SHA-256").digest(blob)).getBytes(Crypto.UTF8), p[4].getBytes(Crypto.UTF8))) return null;
            Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
            ci.init(Cipher.DECRYPT_MODE, new SecretKeySpec(B64.decode(p[3]), "AES"), new GCMParameterSpec(128, Arrays.copyOfRange(blob, 0, 12)));
            byte[] packed = ci.doFinal(blob, 12, blob.length - 12);
            return new Opened(p[1], Long.parseLong(p[2]), new String(gunzip(packed), Crypto.UTF8));
        } catch (Exception e) {
            return null;
        }
    }

    static byte[] gunzip(byte[] b) throws java.io.IOException {
        GZIPInputStream in = new GZIPInputStream(new ByteArrayInputStream(b));
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream(b.length * 4);
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                if (out.size() > MAX_TEXT) throw new java.io.IOException("too big");
            }
            return out.toByteArray();
        } finally {
            in.close();
        }
    }

    static String hex(byte[] b) {
        StringBuilder s = new StringBuilder(b.length * 2);
        for (byte x : b) s.append(String.format("%02x", x & 0xff));
        return s.toString();
    }
}
