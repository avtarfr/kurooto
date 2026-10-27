package io.github.avtarfr.kurooto;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.TimeZone;

/** ChatRules.java on the JVM (0.8.10): Markdown blocks and spans, session ids, the f1 file link, the edit window, the
 *  10 MB limit, titles, date separators and the slash-command list. */
public class ChatTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok  " : "FAIL ") + what);
        if (!ok) failed++;
    }

    public static void main(String[] args) {
        // sessions
        check(ChatRules.isSession("main") && ChatRules.isSession("0123456789abcdef"), "main and 16 hex are sessions");
        check(!ChatRules.isSession("0123456789ABCDEF") && !ChatRules.isSession("abc") && !ChatRules.isSession(null)
                && !ChatRules.isSession("../etc/passwd0000"), "anything else isn't");

        // edit window and size
        long now = 1_800_000_000_000L;
        check(ChatRules.editable(true, now / 1000 - 60, now), "a minute old: editable");
        check(!ChatRules.editable(true, now / 1000 - 16 * 60, now), "16 minutes old: not");
        check(!ChatRules.editable(false, now / 1000, now), "Kurooto's: never");
        check(!ChatRules.tooBig(10L * 1024 * 1024) && ChatRules.tooBig(10L * 1024 * 1024 + 1), "10 MB is the limit");
        check(ChatRules.size(412 * 1024).equals("412 KB") && ChatRules.size(3_565_158).equals("3.4 MB") && ChatRules.size(900).equals("900 B"), "sizes");

        // titles and initials
        check(ChatRules.title("help me outline my thesis on fourier series please").equals("Help me outline my thesis on"), "title: first words");
        check(ChatRules.title("  ").equals("New chat"), "an empty title");
        check(ChatRules.title("**bold** start").equals("Bold start"), "marks dropped");
        check(ChatRules.initials("Thesis outline").equals("TO") && ChatRules.initials("kurooto").equals("K"), "initials");

        // the f1 link
        String[] f = ChatRules.f1("https://line.example.workers.dev/file#i=0123456789abcdef0123456789abcdef&k=AbC-_d&n=sheet%204.pdf");
        check(f != null && f[0].equals("https://line.example.workers.dev/sealed/0123456789abcdef0123456789abcdef"), "f1: where");
        check(f != null && f[1].equals("AbC-_d") && f[2].equals("sheet 4.pdf"), "f1: key and name");
        check(ChatRules.f1("https://line.example/file?i=x") == null, "no fragment: not f1");
        check(ChatRules.f1("http://line.example/file#i=0123456789abcdef&k=a") == null, "not https: refused");
        check(ChatRules.f1("https://line.example/file#i=../../x&k=a") == null, "an odd id: refused");
        check(ChatRules.f1("https://drive.example/view#i=0123456789abcdef&k=a") == null, "not the file page");

        // date separators (UTC, a fixed now: Fri 15 Jan 2027 10:00)
        TimeZone utc = TimeZone.getTimeZone("UTC");
        Calendar c = Calendar.getInstance(utc);
        c.clear();
        c.set(2027, Calendar.JANUARY, 15, 10, 0);
        long nowMs = c.getTimeInMillis(), t = nowMs / 1000;
        check(ChatRules.day(t - 3600, nowMs, utc).equals("Today"), "today");
        check(ChatRules.day(t - 86400, nowMs, utc).equals("Yesterday"), "yesterday");
        check(ChatRules.day(t - 3 * 86400, nowMs, utc).equals("Tuesday"), "a weekday");
        check(ChatRules.day(t - 30 * 86400, nowMs, utc).equals("16 Dec 2026"), "last year: with the year");
        check(ChatRules.when(t - 3600, nowMs, utc).equals("09:00") && ChatRules.when(t - 86400, nowMs, utc).equals("Yest."), "row times");
        check(ChatRules.sameDay(t, t - 3600, utc) && !ChatRules.sameDay(t, t - 86400, utc), "same day");

        // slash commands
        List<String[]> all = new ArrayList<>();
        all.add(new String[] {"help", "What I can do"});
        all.add(new String[] {"/hours", "Study hours"});
        all.add(new String[] {"remind", "A reminder"});
        check(ChatRules.commands(all, "/", 10).size() == 3, "/ lists them all");
        check(ChatRules.commands(all, "/h", 10).size() == 2 && ChatRules.commands(all, "/h", 10).get(1)[0].equals("hours"), "/h: two, slash dropped");
        check(ChatRules.commands(all, "/help me", 10).isEmpty() && ChatRules.commands(all, "hi", 10).isEmpty(), "past the command: none");

        // Markdown blocks
        List<ChatRules.Block> b = ChatRules.blocks("Intro line\nstill intro\n\n- one\n- two\n1. first\n```\ncode **x**\n  indented\n```\n# Head\n> said");
        check(b.size() == 7, "seven blocks (" + b.size() + ")");
        check(b.get(0).kind == ChatRules.PARA && b.get(0).text.equals("Intro line\nstill intro"), "a paragraph keeps its lines");
        check(b.get(1).kind == ChatRules.BULLET && b.get(1).text.equals("one") && b.get(1).marker.equals("•"), "a bullet");
        check(b.get(3).kind == ChatRules.NUMBER && b.get(3).marker.equals("1."), "a numbered item");
        check(b.get(4).kind == ChatRules.CODE && b.get(4).text.equals("code **x**\n  indented"), "code is kept as is");
        check(b.get(5).kind == ChatRules.HEADING && b.get(5).text.equals("Head"), "a heading");
        check(b.get(6).kind == ChatRules.QUOTE && b.get(6).text.equals("said"), "a quote");
        check(ChatRules.blocks("```\nunclosed").get(0).kind == ChatRules.CODE, "an unclosed fence is code");
        check(ChatRules.blocks("**Bold line** here").get(0).kind == ChatRules.PARA, "a bold start isn't a bullet");

        // inline spans
        List<ChatRules.Span> s = ChatRules.inline("a **b** *c* `d` [e](https://x.example/y) _f_ see https://z.example/q.");
        StringBuilder kinds = new StringBuilder();
        for (ChatRules.Span x : s) kinds.append(x.kind);
        check(kinds.toString().equals("0102030402040"), "spans in order (" + kinds + ")");
        check(s.get(7).url.equals("https://x.example/y") && s.get(7).text.equals("e"), "a link's label and address");
        check(s.get(s.size() - 2).url.equals("https://z.example/q"), "a bare address without its full stop");
        check(ChatRules.inline("2*3*4 and snake_case_name").size() == 1, "no italics inside words or sums");
        check(ChatRules.plain("**Hi** _there_\n- `x`").equals("Hi there\n• x"), "plain text");

        System.out.println(failed == 0 ? "chat rules ok" : failed + " failed");
        if (failed > 0) System.exit(1);
    }
}
