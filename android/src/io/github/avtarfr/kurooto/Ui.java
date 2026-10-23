package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.app.Notification;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.StateListDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * Kurooto's look in one place: Material 3 style from the framework alone (no AndroidX). The colours are resources
 * (res/values*: Kurooto's palette, Material You's on Android 12+, light or dark as the system is), the themes are in
 * res/values/themes.xml (Kurooto, Kurooto.Dialog, Kurooto.Call); this class builds the views. A new screen:
 *   LinearLayout col = Ui.page(this);                  // full screen; Ui.dialog(this) under Kurooto.Dialog
 *   col.addView(Ui.headline(this, "Chat"));
 *   LinearLayout card = Ui.card(this);
 *   card.addView(Ui.body(this, "..."));
 *   col.addView(card);
 *   col.addView(Ui.filled(this, "Send"));              // or tonal, outlined, flat
 * Every view comes with LinearLayout params (full width, a small gap above), so addView(v) is enough.
 */
final class Ui {
    static final Typeface MEDIUM = Typeface.create("sans-serif-medium", Typeface.NORMAL);
    static final int MATCH = LinearLayout.LayoutParams.MATCH_PARENT, WRAP = LinearLayout.LayoutParams.WRAP_CONTENT;
    static final float PILL = 999; // a corner radius that makes a pill (GradientDrawable caps it at half the height)

    private Ui() { }

    static int dp(Context c, float v) { return Math.round(v * c.getResources().getDisplayMetrics().density); }

    /** A colour resource (R.color.k_*), as the current theme (light, dark, Material You) has it. */
    static int color(Context c, int res) { return c.getColor(res); }

    static int alpha(int color, float a) { return (color & 0xFFFFFF) | (Math.round(a * 255) << 24); }

    /** Sets v's LinearLayout params: full width, gaps above and below (dp). */
    static <T extends View> T gap(T v, int top, int bottom) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(MATCH, WRAP);
        lp.setMargins(0, dp(v.getContext(), top), 0, dp(v.getContext(), bottom));
        v.setLayoutParams(lp);
        return v;
    }

    /** Shrinks v to its own width at the end of the column: a dialog's quiet actions (Later, Dismiss). */
    static <T extends View> T end(T v) {
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) v.getLayoutParams();
        lp.width = WRAP;
        lp.gravity = Gravity.END;
        return v;
    }

    // ---------- pages ----------
    /** A full-screen page, set as the activity's content: it scrolls, and keeps clear of the status and navigation
     *  bars (Android 15 draws apps behind them). Returns the column to fill. */
    static LinearLayout page(Activity a) {
        ScrollView sv = new ScrollView(a);
        sv.setFitsSystemWindows(true);
        sv.setBackgroundColor(color(a, R.color.k_bg));
        LinearLayout col = column(a);
        col.setPadding(dp(a, 16), dp(a, 24), dp(a, 16), dp(a, 32));
        sv.addView(col, new ScrollView.LayoutParams(MATCH, WRAP));
        a.setContentView(sv);
        return col;
    }

    /** The body of a dialog-themed activity (Kurooto.Dialog): it scrolls, padded like a Material dialog. */
    static LinearLayout dialog(Activity a) {
        ScrollView sv = new ScrollView(a);
        LinearLayout col = column(a);
        col.setPadding(dp(a, 24), dp(a, 20), dp(a, 24), dp(a, 16));
        sv.addView(col, new ScrollView.LayoutParams(MATCH, WRAP));
        a.setContentView(sv);
        return col;
    }

    static LinearLayout column(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    static LinearLayout row(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return gap(l, 0, 0);
    }

    /** A filled card (16dp corners), padded; put text and buttons in it. */
    static LinearLayout card(Context c) {
        LinearLayout k = column(c);
        k.setBackground(shape(color(c, R.color.k_card), 0, dp(c, 16)));
        k.setPadding(dp(c, 16), dp(c, 12), dp(c, 16), dp(c, 16));
        return gap(k, 8, 0);
    }

    /** A card for list rows (item() and the like): no padding of its own, rows' ripples kept inside its corners. */
    static LinearLayout list(Context c) {
        LinearLayout k = column(c);
        k.setBackground(shape(color(c, R.color.k_card), 0, dp(c, 16)));
        k.setPadding(0, dp(c, 4), 0, dp(c, 4));
        k.setClipToOutline(true);
        return gap(k, 8, 0);
    }

    /** A card you tap as a whole (with a ripple), e.g. one question that's waiting. */
    static LinearLayout tapCard(Context c, View.OnClickListener onClick) {
        LinearLayout k = card(c);
        k.setBackground(ripple(color(c, R.color.k_fg), shape(color(c, R.color.k_card), 0, dp(c, 16)), dp(c, 16)));
        k.setOnClickListener(onClick);
        return k;
    }

    /** A two-line list row (title, and a value or explanation under it), 64dp tall at least; tappable if onClick. */
    static LinearLayout item(Context c, String title, String sub, View.OnClickListener onClick) {
        LinearLayout r = column(c);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setMinimumHeight(dp(c, 64));
        r.setPadding(dp(c, 16), dp(c, 8), dp(c, 16), dp(c, 8));
        r.addView(text(c, title, 16, false, color(c, R.color.k_fg)));
        if (sub != null && !sub.isEmpty()) r.addView(text(c, sub, 14, false, color(c, R.color.k_dim)));
        if (onClick != null) {
            r.setBackground(ripple(color(c, R.color.k_fg), null, 0));
            r.setOnClickListener(onClick);
        }
        return gap(r, 0, 0);
    }

    // ---------- text (Material 3's type scale, the parts the app uses) ----------
    static TextView text(Context c, String s, float sp, boolean medium, int colour) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(colour);
        t.setLineSpacing(0, 1.15f);
        if (medium) t.setTypeface(MEDIUM);
        return gap(t, 0, 0);
    }

    /** The screen's name (headline). */
    static TextView headline(Context c, String s) { return gap(text(c, s, 28, false, color(c, R.color.k_fg)), 8, 4); }

    /** A dialog's or card's title. */
    static TextView title(Context c, String s) { return gap(text(c, s, 22, false, color(c, R.color.k_fg)), 0, 8); }

    /** A section's heading, in the accent colour. */
    static TextView heading(Context c, String s) { return gap(text(c, s, 14, true, color(c, R.color.k_primary)), 28, 0); }

    static TextView body(Context c, String s) { return gap(text(c, s, 16, false, color(c, R.color.k_fg)), 4, 4); }

    /** Supporting text: explanations, what something is set to. */
    static TextView dim(Context c, String s) { return gap(text(c, s, 14, false, color(c, R.color.k_dim)), 4, 4); }

    /** Small print under a card. */
    static TextView small(Context c, String s) { return gap(text(c, s, 12, false, color(c, R.color.k_dim)), 8, 0); }

    /** A line for "Sending…", "Sent." and errors; colour it with ok() or bad(). */
    static TextView status(Context c) { return gap(text(c, "", 14, false, color(c, R.color.k_dim)), 8, 0); }

    static void ok(TextView t) { t.setTextColor(color(t.getContext(), R.color.k_ok)); }

    static void bad(TextView t) { t.setTextColor(color(t.getContext(), R.color.k_bad)); }

    /** Cuts a long text to a few lines with "…". */
    static TextView lines(TextView t, int n) {
        t.setMaxLines(n);
        t.setEllipsize(TextUtils.TruncateAt.END);
        return t;
    }

    // ---------- buttons (pills, 48dp tall at least, full width) ----------
    /** The main thing to do. */
    static Button filled(Context c, String s) { return button(c, s, color(c, R.color.k_primary), color(c, R.color.k_on_primary), 0); }

    /** Something to do, quieter than filled. */
    static Button tonal(Context c, String s) { return button(c, s, color(c, R.color.k_tonal), color(c, R.color.k_on_tonal), 0); }

    static Button outlined(Context c, String s) { return button(c, s, 0, color(c, R.color.k_primary), color(c, R.color.k_outline)); }

    /** A text button: Later, Dismiss, Fix. */
    static Button flat(Context c, String s) {
        Button b = button(c, s, 0, color(c, R.color.k_primary), 0);
        b.setPadding(dp(c, 12), 0, dp(c, 12), 0);
        return b;
    }

    /** A taller button for the screen's one big action (Call, Answer). */
    static Button large(Button b) {
        b.setMinHeight(dp(b.getContext(), 56));
        b.setMinimumHeight(dp(b.getContext(), 56));
        b.setTextSize(16);
        return b;
    }

    /** Any button: fill and outline colours (0 for none) and the text's colour. Greyed out when disabled. */
    static Button button(Context c, String s, int fill, int ink, int stroke) {
        Button b = new Button(c);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(15);
        b.setTypeface(MEDIUM);
        b.setGravity(Gravity.CENTER);
        b.setStateListAnimator(null); // flat, no shadow
        b.setMinHeight(dp(c, 48));
        b.setMinimumHeight(dp(c, 48));
        b.setMinWidth(dp(c, 48));
        b.setMinimumWidth(dp(c, 48));
        int off = color(c, R.color.k_fg);
        b.setTextColor(states(ink, alpha(off, .38f)));
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(PILL);
        g.setColor(states(fill, fill == 0 ? 0 : alpha(off, .12f)));
        if (stroke != 0) g.setStroke(dp(c, 1), states(stroke, alpha(off, .12f)));
        b.setBackground(ripple(ink, g, PILL));
        b.setPadding(dp(c, 24), dp(c, 10), dp(c, 24), dp(c, 10));
        return gap(b, 8, 0);
    }

    /** An outlined text field: a thin outline, a thicker one in the accent colour while you type. */
    static EditText field(Context c, String hint) {
        EditText e = new EditText(c);
        e.setHint(hint);
        e.setTextSize(16);
        e.setTextColor(color(c, R.color.k_fg));
        e.setHintTextColor(color(c, R.color.k_dim));
        StateListDrawable bg = new StateListDrawable();
        bg.addState(new int[]{android.R.attr.state_focused}, shape(0, color(c, R.color.k_primary), dp(c, 12), dp(c, 2)));
        bg.addState(new int[]{}, shape(0, color(c, R.color.k_outline), dp(c, 12), dp(c, 1)));
        e.setBackground(bg);
        e.setPadding(dp(c, 16), dp(c, 14), dp(c, 16), dp(c, 14));
        e.setMinHeight(dp(c, 56));
        return gap(e, 8, 0);
    }

    /** A small icon (res/drawable), tinted. */
    static ImageView icon(Context c, int res, int tint) {
        ImageView i = new ImageView(c);
        i.setImageResource(res);
        i.setColorFilter(tint);
        return i;
    }

    // ---------- dialogs that wait on something ----------
    /** A dialog's whole body while it works: a title, then a spinner beside a line of status. Returns the status
     *  line; done() stops the spinner. */
    static TextView busy(Activity a, String title, String text) {
        LinearLayout col = dialog(a);
        col.addView(title(a, title));
        LinearLayout r = row(a);
        ProgressBar p = new ProgressBar(a);
        p.setIndeterminateTintList(ColorStateList.valueOf(color(a, R.color.k_primary)));
        r.addView(p, new LinearLayout.LayoutParams(dp(a, 32), dp(a, 32)));
        TextView t = text(a, text, 16, false, color(a, R.color.k_fg));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, WRAP, 1);
        lp.setMargins(dp(a, 16), dp(a, 8), 0, dp(a, 8));
        r.addView(t, lp);
        col.addView(r);
        t.setTag(p);
        return t;
    }

    /** Stops busy()'s spinner; the status turns green if it worked, red if not. */
    static void done(TextView status, boolean worked) {
        if (status.getTag() instanceof View) ((View) status.getTag()).setVisibility(View.GONE);
        if (worked) ok(status); else bad(status);
    }

    // ---------- notifications ----------
    /** Kurooto's accent on a notification (its icon and name; Android 5+ shows it). */
    static Notification.Builder tint(Context c, Notification.Builder b) { return b.setColor(color(c, R.color.k_brand)); }

    // ---------- drawables ----------
    /** A rounded rectangle: fill and outline colours (0 for none), corner radius and outline width in pixels. */
    static GradientDrawable shape(int fill, int stroke, float radius, int strokeWidth) {
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(radius);
        g.setColor(fill);
        if (stroke != 0) g.setStroke(strokeWidth, stroke);
        return g;
    }

    static GradientDrawable shape(int fill, int stroke, float radius) { return shape(fill, stroke, radius, 1); }

    /** A circle, e.g. behind an icon. */
    static GradientDrawable circle(int fill) {
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(fill);
        return g;
    }

    /** content with a ripple in ink's colour when pressed, kept inside the given corner radius. */
    static RippleDrawable ripple(int ink, Drawable content, float radius) {
        return new RippleDrawable(ColorStateList.valueOf(alpha(ink, .2f)), content, shape(Color.WHITE, 0, radius));
    }

    private static ColorStateList states(int normal, int disabled) {
        return new ColorStateList(new int[][]{{-android.R.attr.state_enabled}, {}}, new int[]{disabled, normal});
    }
}
