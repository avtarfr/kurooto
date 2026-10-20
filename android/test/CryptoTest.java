package io.github.avtarfr.kurooto;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** The app's k1 code against the shared test vectors (tests/fixtures/call-vectors.json), on a plain JVM:
 *  android/build.sh --test. (The vectors file is written with indent=2; sections end at "\n  }".) */
public final class CryptoTest {
    private static String field(String json, String section, String name) {
        Matcher m = Pattern.compile("\"" + section + "\"\\s*:\\s*\\{(.*?)\\n  \\}", Pattern.DOTALL).matcher(json);
        if (!m.find()) throw new IllegalStateException("no " + section);
        Matcher f = Pattern.compile("\"" + name + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"").matcher(m.group(1));
        if (!f.find()) throw new IllegalStateException("no " + section + "." + name);
        return f.group(1).replace("\\\"", "\"").replace("\\\\", "\\");
    }

    private static void check(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
        System.out.println("ok  " + what);
    }

    public static void main(String[] args) throws Exception {
        String json = new String(Files.readAllBytes(Paths.get(args[0])), "UTF-8");
        byte[] key = B64.decode(field(json, "k1", "key"));
        String plain = field(json, "k1", "plain"), sealed = field(json, "k1", "sealed");
        String nonceHex = field(json, "k1", "nonce_hex");
        byte[] nonce = new byte[nonceHex.length() / 2];
        for (int i = 0; i < nonce.length; i++) nonce[i] = (byte) Integer.parseInt(nonceHex.substring(2 * i, 2 * i + 2), 16);
        check(sealed.equals(Crypto.seal(key, plain, nonce)), "sealing gives the same bytes as Python and the Worker");
        check(plain.equals(Crypto.open(key, sealed)), "opening a message sealed elsewhere");
        check(Crypto.open(key, sealed.substring(0, sealed.length() - 2) + "AA") == null, "a changed message is refused");
        check(Crypto.open(new byte[32], sealed) == null, "another key can't open it");
        check(plain.equals(Crypto.open(key, Crypto.seal(key, plain))), "round trip with a random nonce");
        byte[] all = new byte[256];
        for (int i = 0; i < 256; i++) all[i] = (byte) i;
        check(java.util.Arrays.equals(all, B64.decode(B64.encode(all, true))), "base64url round trip");
        check(java.util.Arrays.equals(all, B64.decode(B64.encode(all, false))), "base64 round trip");
        check(B64.encode(key, false).equals(java.util.Base64.getEncoder().encodeToString(key)), "base64 matches the JDK's");
        sealedReminders(json);
    }

    /** s1: a reminder your computer sealed for this phone alone (Seal). */
    private static void sealedReminders(String json) throws Exception {
        java.security.KeyPair mine = Seal.newKeys();
        java.security.spec.ECParameterSpec params = ((java.security.interfaces.ECPublicKey) mine.getPublic()).getParams();
        java.security.PrivateKey phone = java.security.KeyFactory.getInstance("EC").generatePrivate(
                new java.security.spec.ECPrivateKeySpec(new java.math.BigInteger(field(json, "s1", "phone_priv_hex"), 16), params));
        String plain = field(json, "s1", "plain"), sealed = field(json, "s1", "sealed"), pub = field(json, "s1", "phone_pub");
        check(plain.equals(Seal.open(phone, params, sealed)), "opening a reminder sealed for this phone on the computer");
        check(Seal.open(phone, params, sealed.substring(0, sealed.length() - 2) + "AA") == null, "a changed reminder is refused");
        check(Seal.open(mine.getPrivate(), params, sealed) == null, "another phone can't open it");
        check(Seal.open(phone, params, "k1." + sealed.substring(3)) == null, "only s1 tokens");
        java.security.interfaces.ECPublicKey back = Seal.fromRaw(B64.decode(pub), params);
        check(B64.encode(Seal.raw(back), true).equals(pub), "the public key's 65 bytes round trip");
        check(Seal.raw((java.security.interfaces.ECPublicKey) mine.getPublic()).length == 65, "a new key is a P-256 point");
    }
}
