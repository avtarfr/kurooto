# R8 for release builds: only the libraries (Compose, AndroidX) shrink. The app's own classes stay whole, so nothing
# reached by reflection, from the manifest or from the call page's JavaScript can go missing.
-keep class io.github.avtarfr.kurooto.** { *; }
# the call page's bridge (CallActivity): its @JavascriptInterface methods, in any class
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
