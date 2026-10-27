package io.github.avtarfr.kurooto;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The chat's rules that need no Android (0.8.10), so `build.sh --test` checks them on the JVM (test/ChatTest.java):
 * the Markdown the bubbles show (blocks and inline spans), session ids, the sealed file links ("f1": the key only in
 * the #fragment), how long your own message stays editable, the 10 MB limit, a new chat's title from its first words,
 * the date separators and the slash-command list.
 */
final class ChatRules {
    private ChatRules() { }

    static final String MAIN = "main";
    /** Files the chat carries, at most (the call line's limit). */
    static final long FILE_MAX = 10L * 1024 * 1024;
    /** Your own message can be edited for this long after it was sent. */
    static final long EDIT_MS = 15 * 60 * 1000L;
    private static final Pattern SESSION = Pattern.compile("[0-9a-f]{16}");

    /** A session id the protocol takes: 16 hex characters, or "main". */
    static boolean isSession(String s) {
        return s != null && (MAIN.equals(s) || SESSION.matcher(s).matches());
    }

    static boolean editable(boolean mine, long atSec, long nowMs) {
        return mine && atSec > 0 && nowMs - atSec * 1000 <= EDIT_MS && nowMs - atSec * 1000 >= -60_000;
    }

    static boolean tooBig(long size) {
        return size > FILE_MAX;
    }

    /** "412 KB", "3.4 MB", "900 B". */
    static String size(long n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return Math.round(n / 1024.0) + " KB";
        double mb = n / (1024.0 * 1024);
        return (mb < 10 ? String.format(Locale.ROOT, "%.1f", mb) : String.valueOf(Math.round(mb))) + " MB";
    }

    /** A chat's title from its first message, as the computer makes it: the first few words. */
    static String title(String text) {
        String t = text == null ? "" : text.replaceAll("[*_`#>\\[\\]()]", " ").trim().replaceAll("\\s+", " ");
        if (t.isEmpty()) return "New chat";
        String[] w = t.split(" ");
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < w.length && i < 6; i++) {
            if (s.length() + w[i].length() > 40) break;
            if (s.length() > 0) s.append(' ');
            s.append(w[i]);
        }
        if (s.length() == 0) s.append(t, 0, Math.min(40, t.length()));
        return Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }

    /** The two letters on a chat's avatar: the first letters of its first two words ("TO" for "Thesis outline"). */
    static String initials(String title) {
        String t = title == null ? "" : title.trim();
        if (t.isEmpty()) return "?";
        String[] w = t.split("\\s+");
        int a = t.codePointAt(0);
        String s = new String(Character.toChars(a));
        if (w.length > 1 && !w[1].isEmpty() && Character.isLetterOrDigit(w[1].codePointAt(0))) s += new String(Character.toChars(w[1].codePointAt(0)));
        return s.toUpperCase(Locale.ROOT);
    }

    // ------------------------------------------------------------------------------------- the f1 link
    /** A sealed file link from the computer: {where to fetch it, the key (base64url), the name}, or null. The link is
     *  "<line>/file#i=<fid>&k=<key>&n=<name>"; the sealed bytes are at "<line>/sealed/<fid>". */
    static String[] f1(String url) {
        if (url == null || !url.startsWith("https://")) return null;
        int hash = url.indexOf('#');
        if (hash < 0) return null;
        String base = url.substring(0, hash), frag = url.substring(hash + 1);
        if (!base.endsWith("/file")) return null;
        String i = null, k = null, n = "";
        for (String kv : frag.split("&")) {
            int eq = kv.indexOf('=');
            if (eq < 0) continue;
            String key = kv.substring(0, eq), v = decode(kv.substring(eq + 1));
            if ("i".equals(key)) i = v;
            else if ("k".equals(key)) k = v;
            else if ("n".equals(key)) n = v;
        }
        if (i == null || k == null || !i.matches("[A-Za-z0-9_-]{8,64}")) return null;
        return new String[] {base.substring(0, base.length() - "/file".length()) + "/sealed/" + i, k, n};
    }

    private static String decode(String s) {
        try {
            return java.net.URLDecoder.decode(s, "UTF-8");
        } catch (Exception e) {
            return s;
        }
    }

    // ----------------------------------------------------------------------------------- date separators
    /** The separator over a day's messages: "Today", "Yesterday", the weekday within a week, else "3 Oct" (this
     *  year) or "3 Oct 2025". */
    static String day(long atSec, long nowMs, TimeZone tz) {
        Calendar a = Calendar.getInstance(tz, Locale.ENGLISH), n = Calendar.getInstance(tz, Locale.ENGLISH);
        a.setTimeInMillis(atSec * 1000);
        n.setTimeInMillis(nowMs);
        int days = daysBetween(a, n);
        if (days == 0) return "Today";
        if (days == 1) return "Yesterday";
        if (days > 1 && days < 7) return a.getDisplayName(Calendar.DAY_OF_WEEK, Calendar.LONG, Locale.ENGLISH);
        String m = a.getDisplayName(Calendar.MONTH, Calendar.SHORT, Locale.ENGLISH);
        String s = a.get(Calendar.DAY_OF_MONTH) + " " + m;
        return a.get(Calendar.YEAR) == n.get(Calendar.YEAR) ? s : s + " " + a.get(Calendar.YEAR);
    }

    /** The same calendar day. */
    static boolean sameDay(long aSec, long bSec, TimeZone tz) {
        Calendar a = Calendar.getInstance(tz), b = Calendar.getInstance(tz);
        a.setTimeInMillis(aSec * 1000);
        b.setTimeInMillis(bSec * 1000);
        return daysBetween(a, b) == 0;
    }

    private static int daysBetween(Calendar a, Calendar b) {
        Calendar x = (Calendar) a.clone(), y = (Calendar) b.clone();
        for (Calendar c : new Calendar[] {x, y}) {
            c.set(Calendar.HOUR_OF_DAY, 12);
            c.set(Calendar.MINUTE, 0);
            c.set(Calendar.SECOND, 0);
            c.set(Calendar.MILLISECOND, 0);
        }
        return (int) Math.round((y.getTimeInMillis() - x.getTimeInMillis()) / 86_400_000.0);
    }

    /** "10:12" today, "Yest." for yesterday, "Mon" within the week, "3 Oct" before: the time on a chat's row. */
    static String when(long atSec, long nowMs, TimeZone tz) {
        String d = day(atSec, nowMs, tz);
        if ("Today".equals(d)) {
            Calendar a = Calendar.getInstance(tz);
            a.setTimeInMillis(atSec * 1000);
            return String.format(Locale.ROOT, "%02d:%02d", a.get(Calendar.HOUR_OF_DAY), a.get(Calendar.MINUTE));
        }
        if ("Yesterday".equals(d)) return "Yest.";
        if (d.indexOf(' ') < 0) return d.substring(0, 3);
        return d;
    }

    // ----------------------------------------------------------------------------------- slash commands
    /** The commands to list while you type "/…": those whose name starts with what's typed (without the slash), at
     *  most `max`; none once there's a space (you're past the command). Each is {name, help}. */
    static List<String[]> commands(List<String[]> all, String typed, int max) {
        List<String[]> out = new ArrayList<>();
        if (typed == null || !typed.startsWith("/") || typed.contains(" ") || typed.contains("\n")) return out;
        String q = typed.substring(1).toLowerCase(Locale.ROOT);
        for (String[] c : all) {
            String n = c[0].startsWith("/") ? c[0].substring(1) : c[0];
            if (n.toLowerCase(Locale.ROOT).startsWith(q)) out.add(new String[] {n, c.length > 1 ? c[1] : ""});
            if (out.size() >= max) break;
        }
        return out;
    }

    // ------------------------------------------------------------------------------------------ Markdown
    static final int PARA = 0, CODE = 1, BULLET = 2, NUMBER = 3, HEADING = 4, QUOTE = 5;

    /** A block of a message: a paragraph, a fenced code block, a list item (marker: "•" or "3."), a heading, a quote. */
    static final class Block {
        final int kind;
        final String text, marker;
        Block(int kind, String text, String marker) { this.kind = kind; this.text = text; this.marker = marker; }
    }

    private static final Pattern BULLET_RE = Pattern.compile("^\\s{0,6}[-*+]\\s+(.*)$");
    private static final Pattern NUMBER_RE = Pattern.compile("^\\s{0,6}(\\d{1,3})[.)]\\s+(.*)$");
    private static final Pattern HEADING_RE = Pattern.compile("^#{1,4}\\s+(.*)$");

    static List<Block> blocks(String text) {
        List<Block> out = new ArrayList<>();
        if (text == null) return out;
        String[] lines = text.replace("\r\n", "\n").split("\n", -1);
        StringBuilder para = new StringBuilder(), code = null;
        for (String line : lines) {
            if (code != null) {
                if (line.trim().startsWith("```")) {
                    out.add(new Block(CODE, trimEnd(code.toString()), ""));
                    code = null;
                } else {
                    if (code.length() > 0) code.append('\n');
                    code.append(line);
                }
                continue;
            }
            if (line.trim().startsWith("```")) {
                flush(out, para);
                code = new StringBuilder();
                continue;
            }
            Matcher m;
            if ((m = BULLET_RE.matcher(line)).matches() && !line.trim().startsWith("**")) {
                flush(out, para);
                out.add(new Block(BULLET, m.group(1), "•"));
            } else if ((m = NUMBER_RE.matcher(line)).matches()) {
                flush(out, para);
                out.add(new Block(NUMBER, m.group(2), m.group(1) + "."));
            } else if ((m = HEADING_RE.matcher(line)).matches()) {
                flush(out, para);
                out.add(new Block(HEADING, m.group(1), ""));
            } else if (line.startsWith("> ") || line.equals(">")) {
                flush(out, para);
                out.add(new Block(QUOTE, line.length() > 2 ? line.substring(2) : "", ""));
            } else if (line.trim().isEmpty()) {
                flush(out, para);
            } else {
                if (para.length() > 0) para.append('\n');
                para.append(line);
            }
        }
        if (code != null) out.add(new Block(CODE, trimEnd(code.toString()), "")); // an unclosed fence: still code
        flush(out, para);
        return out;
    }

    private static void flush(List<Block> out, StringBuilder para) {
        if (para.length() == 0) return;
        out.add(new Block(PARA, para.toString(), ""));
        para.setLength(0);
    }

    private static String trimEnd(String s) {
        int e = s.length();
        while (e > 0 && Character.isWhitespace(s.charAt(e - 1))) e--;
        return s.substring(0, e);
    }

    static final int TEXT = 0, BOLD = 1, ITALIC = 2, MONO = 3, LINK = 4, BOLD_ITALIC = 5;

    /** A run of text with one style; a link has its address. */
    static final class Span {
        final int kind;
        final String text, url;
        Span(int kind, String text, String url) { this.kind = kind; this.text = text; this.url = url; }
    }

    private static final Pattern INLINE = Pattern.compile(
            "`([^`\\n]+)`" // 1 code
            + "|\\*\\*\\*([^*\\n]+?)\\*\\*\\*" // 2 bold italic
            + "|\\*\\*([^*\\n]+?)\\*\\*" // 3 bold
            + "|__([^_\\n]+?)__" // 4 bold
            + "|\\[([^\\]\\n]+)\\]\\((https?://[^)\\s]+)\\)" // 5, 6 a link
            + "|(?<![\\w*])\\*([^*\\s][^*\\n]*?)\\*(?![\\w*])" // 7 italic
            + "|(?<![\\w_])_([^_\\s][^_\\n]*?)_(?![\\w_])" // 8 italic
            + "|(https?://[^\\s<>\"]+[^\\s<>\".,;:!?)\\]])"); // 9 a bare address

    static List<Span> inline(String text) {
        List<Span> out = new ArrayList<>();
        if (text == null || text.isEmpty()) return out;
        Matcher m = INLINE.matcher(text);
        int at = 0;
        while (m.find()) {
            if (m.start() > at) out.add(new Span(TEXT, text.substring(at, m.start()), null));
            if (m.group(1) != null) out.add(new Span(MONO, m.group(1), null));
            else if (m.group(2) != null) out.add(new Span(BOLD_ITALIC, m.group(2), null));
            else if (m.group(3) != null) out.add(new Span(BOLD, m.group(3), null));
            else if (m.group(4) != null) out.add(new Span(BOLD, m.group(4), null));
            else if (m.group(5) != null) out.add(new Span(LINK, m.group(5), m.group(6)));
            else if (m.group(7) != null) out.add(new Span(ITALIC, m.group(7), null));
            else if (m.group(8) != null) out.add(new Span(ITALIC, m.group(8), null));
            else out.add(new Span(LINK, m.group(9), m.group(9)));
            at = m.end();
        }
        if (at < text.length()) out.add(new Span(TEXT, text.substring(at), null));
        return out;
    }

    /** The text without its Markdown marks (what Copy and Share give, and a chat's last line). */
    static String plain(String text) {
        StringBuilder s = new StringBuilder();
        for (Block b : blocks(text)) {
            if (s.length() > 0) s.append('\n');
            if (b.kind == CODE) { s.append(b.text); continue; }
            if (b.kind == BULLET || b.kind == NUMBER) s.append(b.marker).append(' ');
            for (Span x : inline(b.text)) s.append(x.text);
        }
        return s.toString();
    }
}
