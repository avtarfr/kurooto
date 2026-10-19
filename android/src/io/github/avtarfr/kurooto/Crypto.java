package io.github.avtarfr.kurooto;

import java.nio.charset.Charset;
import java.security.SecureRandom;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * "k1." messages from your call line over ntfy: AES-256-GCM, "k1." + base64url(nonce || ciphertext+tag).
 * The same format as the Worker (worker.js) and Kurooto on your computer (calls/line.py); the shared test
 * vectors (tests/fixtures/call-vectors.json) check all three. The key comes from pairing, never from the APK.
 */
final class Crypto {
    static final Charset UTF8 = Charset.forName("UTF-8");

    private Crypto() { }

    static String seal(byte[] key, String plain) {
        byte[] nonce = new byte[12];
        new SecureRandom().nextBytes(nonce);
        return seal(key, plain, nonce);
    }

    static String seal(byte[] key, String plain, byte[] nonce) {
        try {
            Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
            ci.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key, "AES"), new GCMParameterSpec(128, nonce));
            byte[] ct = ci.doFinal(plain.getBytes(UTF8));
            byte[] all = new byte[12 + ct.length];
            System.arraycopy(nonce, 0, all, 0, 12);
            System.arraycopy(ct, 0, all, 12, ct.length);
            return "k1." + B64.encode(all, true);
        } catch (Exception e) {
            return null;
        }
    }

    /** The plain text, or null if it isn't ours (another key) or was changed on the way. */
    static String open(byte[] key, String token) {
        if (key == null || key.length == 0 || token == null || !token.startsWith("k1.")) return null;
        try {
            byte[] all = B64.decode(token.substring(3));
            Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
            ci.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"), new GCMParameterSpec(128, Arrays.copyOfRange(all, 0, 12)));
            return new String(ci.doFinal(all, 12, all.length - 12), UTF8);
        } catch (Exception e) {
            return null;
        }
    }
}
