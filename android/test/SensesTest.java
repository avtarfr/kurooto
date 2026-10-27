package io.github.avtarfr.kurooto;

import java.util.ArrayList;
import java.util.List;

/** The phone senses' plain rules (0.8.0): motion, light, bins, the Wi-Fi hash, what is held. */
public class SensesTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        if (!ok) { failed++; System.out.println("FAIL: " + what); }
    }

    public static void main(String[] a) {
        check(SensesRules.motion(10, 1.5).equals("walking"), "steps and shaking: walking");
        check(SensesRules.motion(0, 0.02).equals("still"), "nothing: still");
        check(SensesRules.motion(0, 0.4).equals("vehicle"), "a steady shake without steps: a vehicle");
        check(!SensesRules.motion(1, 0.5).equals("walking"), "one step is not walking");
        check(SensesRules.light(2).equals("dark") && SensesRules.light(50).equals("dim") && SensesRules.light(500).equals("bright"), "light bands");
        check(Math.abs(SensesRules.spread(new double[]{9.8, 9.8, 9.8})) < 1e-9, "no shake: no spread");
        check(SensesRules.spread(new double[]{9, 11, 9, 11}) > 0.9, "shaking has spread");
        check(SensesRules.spread(new double[]{1}) == 0, "one sample has no spread");
        check(SensesRules.bin(1_000_000_123L) % SensesRules.BIN_MS == 0, "bins start on five minutes");
        String h1 = SensesRules.wifiId("salt-a", "HomeNet"), h2 = SensesRules.wifiId("salt-b", "HomeNet");
        check(h1.length() == 12 && !h1.equals(h2), "the hash depends on this phone's salt");
        check(h1.equals(SensesRules.wifiId("salt-a", "HomeNet")) && !h1.contains("Home"), "stable, and never the name");
        check(SensesRules.wifiId("s", "<unknown ssid>").isEmpty() && SensesRules.wifiId("s", "").isEmpty(), "no name, no id");
        String b = SensesRules.bin("steps", 1_000_000_123L, new String[]{"total"}, new Object[]{4200});
        check(b.equals("{\"s\":\"steps\",\"t\":" + SensesRules.bin(1_000_000_123L) + ",\"total\":4200}"), "a bin's shape: " + b);
        String w = SensesRules.bin("places", 5, new String[]{"event", "label"}, new Object[]{"arrive", "the \"lab\"\n"});
        check(w.contains("\"label\":\"the  lab\"") || !w.contains("\n"), "quotes and newlines can't break the JSON: " + w);
        check(SensesRules.bin("microphone", 5, new String[]{"level"}, new Object[]{3}).isEmpty(), "no microphone sensor exists");
        check(!SensesRules.known("microphone") && SensesRules.known("usage"), "the sensor list");
        List<String> held = new ArrayList<>();
        held = SensesRules.keep(held, SensesRules.bin("steps", 300_000L, new String[]{"total"}, new Object[]{10}), 5);
        held = SensesRules.keep(held, SensesRules.bin("steps", 300_500L, new String[]{"total"}, new Object[]{20}), 5);
        check(held.size() == 1 && held.get(0).contains("\"total\":20"), "the same bin is replaced by the later reading");
        for (int i = 0; i < 10; i++) held = SensesRules.keep(held, SensesRules.bin("light", i * 300_000L + 1_000_000L, new String[]{"band"}, new Object[]{"dim"}), 5);
        check(held.size() == 5, "past the limit the oldest go");
        // 0.8.13: a batch kept on the line holds the phone back only while it still waits there, never by the clock
        check(SensesRules.maySend("", null) && SensesRules.maySend(null, null), "nothing on the line: send");
        check(!SensesRules.maySend("a1", java.util.Arrays.asList("x9", "a1")), "the batch still waits on the line: hold");
        check(SensesRules.maySend("a1", java.util.Arrays.asList("x9")), "your computer took the batch: send again at once");
        check(SensesRules.maySend("a1", new ArrayList<>()), "the line holds nothing from this phone: send");
        check(!SensesRules.maySend("a1", null), "the line can't be asked: hold, ask again next time");
        if (failed > 0) { System.out.println(failed + " failed"); System.exit(1); }
        System.out.println("SensesTest ok");
    }
}
