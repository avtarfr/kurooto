package io.github.avtarfr.kurooto;

import android.app.Application;

public class App extends Application {
    @Override public void onCreate() {
        super.onCreate();
        Tls.install(this);
        Senses.schedule(this); // the senses you switched on (Phone tab) keep their 15-minute alarm
        Senses.watchUnlocks(this);
        Places.restore(this); // location reminders' alerts don't survive a restart or an update
    }
}
