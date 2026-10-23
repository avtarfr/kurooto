package io.github.avtarfr.kurooto;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Systems and the Notes map (0.7.0): ViewSeal opens a "v1" snapshot your computer sealed for this phone, against
 *  the shared vectors (tests/fixtures/call-vectors.json, "v1"), on a plain JVM: android/build.sh --test. */
public final class ViewsTest {
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
        java.security.KeyPair other = Seal.newKeys();
        java.security.spec.ECParameterSpec params = ((java.security.interfaces.ECPublicKey) other.getPublic()).getParams();
        java.security.PrivateKey phone = java.security.KeyFactory.getInstance("EC").generatePrivate(
                new java.security.spec.ECPrivateKeySpec(new java.math.BigInteger(field(json, "s1", "phone_priv_hex"), 16), params));
        String head = field(json, "v1", "head_sealed"), plain = field(json, "v1", "plain");
        byte[] blob = B64.decode(field(json, "v1", "blob"));
        ViewSeal.Opened o = ViewSeal.open(phone, params, head, blob);
        check(o != null && plain.equals(o.text), "opening a snapshot sealed for this phone on the computer (gzip and all)");
        check(o != null && "notes".equals(o.kind) && o.rev == 1760000200123456L, "its kind and hand-over number");
        check(ViewSeal.open(other.getPrivate(), params, head, blob) == null, "another phone can't open it");
        byte[] changed = blob.clone();
        changed[changed.length - 1] ^= 1;
        check(ViewSeal.open(phone, params, head, changed) == null, "a changed snapshot is refused");
        check(ViewSeal.open(phone, params, head, java.util.Arrays.copyOf(blob, blob.length - 4)) == null, "a cut one too");
        check(ViewSeal.open(phone, params, field(json, "s1", "sealed"), blob) == null, "a head that isn't a view's is refused");
    }
}
