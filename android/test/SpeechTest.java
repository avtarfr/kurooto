package io.github.avtarfr.kurooto;

/** Speech.java on the JVM: what was heard reaches the call page as one quoted string, whatever it contains. */
public class SpeechTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok  " : "FAIL ") + what);
        if (!ok) failed++;
    }

    public static void main(String[] args) {
        check(Speech.js("heard", "hello").equals("window.kurootoSpeech&&window.kurootoSpeech.heard(\"hello\")"),
                "a plain answer");
        String evil = "\");alert(1);//</script><script>x=' \n\\";
        String q = Speech.quote(evil);
        check(q.startsWith("\"") && q.endsWith("\""), "quoted");
        String inner = q.substring(1, q.length() - 1);
        boolean breaks = false;
        for (int i = 0; i < inner.length(); i++) {
            char c = inner.charAt(i);
            if (c == '"' && (i == 0 || inner.charAt(i - 1) != '\\')) breaks = true;
            if (c == '<' || c == '>' || c == '\'' || c == '\n' || c == ' ') breaks = true;
        }
        check(!breaks, "nothing in it ends the string or the script");
        check(Speech.quote("a\\\"b").equals("\"a\\\\\\\"b\""), "backslash before a quote");
        check(Speech.quote(null).equals("\"\""), "nothing heard");
        check(Speech.quote("héllo नमस्ते").equals("\"héllo नमस्ते\""), "other languages pass as they are");
        check(Speech.error(6).equals("no-speech") && Speech.error(7).equals("no-match"), "silence is nothing heard");
        check(Speech.error(9).equals("permission") && Speech.error(13).equals("language"), "errors the page acts on");
        check(Speech.tryService(13) && !Speech.tryService(7) && !Speech.tryService(5), "when to try the speech service");
        if (failed > 0) System.exit(1);
    }
}
