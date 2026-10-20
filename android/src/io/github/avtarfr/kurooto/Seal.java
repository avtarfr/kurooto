package io.github.avtarfr.kurooto;

import java.math.BigInteger;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.interfaces.ECPublicKey;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPublicKeySpec;
import java.util.Arrays;

import javax.crypto.KeyAgreement;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * "s1." reminders: what your computer hands your call line for when it's asleep, sealed for this phone alone.
 * This phone makes its own P-256 key pair (Prefs keeps it; the private half never leaves the phone) and gives the call
 * line only the public half. Your computer seals each reminder to it with a fresh key: ECDH, HKDF-SHA256 (salt: the
 * fresh public key, info "kurooto s1") to an AES-256 key, then the same k1 format as everything else (Crypto). So
 * the call line keeps them and sends them at their time, but can't read them.
 *   "s1." + base64url(fresh public key, 65 bytes uncompressed) + "." + base64url(nonce || ciphertext+tag)
 * The same as Kurooto on your computer (calls/line.py); tests/fixtures/call-vectors.json pins both. No Android
 * classes here, so android/build.sh --test runs it on a plain JVM.
 */
final class Seal {
    static final byte[] INFO = "kurooto s1".getBytes(Crypto.UTF8);

    private Seal() { }

    static KeyPair newKeys() throws Exception {
        KeyPairGenerator g = KeyPairGenerator.getInstance("EC");
        g.initialize(new ECGenParameterSpec("secp256r1"));
        return g.generateKeyPair();
    }

    /** A public key as the call line keeps it: 0x04 || x || y (65 bytes). */
    static byte[] raw(ECPublicKey k) {
        byte[] out = new byte[65];
        out[0] = 4;
        System.arraycopy(fixed(k.getW().getAffineX()), 0, out, 1, 32);
        System.arraycopy(fixed(k.getW().getAffineY()), 0, out, 33, 32);
        return out;
    }

    static ECPublicKey fromRaw(byte[] raw, ECParameterSpec params) throws Exception {
        if (raw.length != 65 || raw[0] != 4) throw new IllegalArgumentException("not a P-256 point");
        ECPoint w = new ECPoint(new BigInteger(1, Arrays.copyOfRange(raw, 1, 33)), new BigInteger(1, Arrays.copyOfRange(raw, 33, 65)));
        return (ECPublicKey) KeyFactory.getInstance("EC").generatePublic(new ECPublicKeySpec(w, params));
    }

    private static byte[] fixed(BigInteger v) {
        byte[] b = v.toByteArray(), out = new byte[32];
        int n = Math.min(b.length, 32);
        System.arraycopy(b, b.length - n, out, 32 - n, n);
        return out;
    }

    /** HKDF-SHA256 (RFC 5869) for up to 32 bytes: one HMAC block. */
    static byte[] hkdf(byte[] ikm, byte[] salt, byte[] info, int n) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(salt, "HmacSHA256"));
        byte[] prk = mac.doFinal(ikm);
        mac.init(new SecretKeySpec(prk, "HmacSHA256"));
        mac.update(info);
        mac.update((byte) 1);
        return Arrays.copyOf(mac.doFinal(), n);
    }

    /** The plain text, or null if it isn't sealed for this key (another phone's) or was changed on the way. */
    static String open(PrivateKey mine, ECParameterSpec params, String token) {
        if (mine == null || token == null || !token.startsWith("s1.")) return null;
        String[] parts = token.split("\\.");
        if (parts.length != 3) return null;
        try {
            byte[] epk = B64.decode(parts[1]);
            KeyAgreement ka = KeyAgreement.getInstance("ECDH");
            ka.init(mine);
            ka.doPhase(fromRaw(epk, params), true);
            byte[] key = hkdf(ka.generateSecret(), epk, INFO, 32);
            return Crypto.open(key, "k1." + parts[2]);
        } catch (Exception e) {
            return null;
        }
    }
}
