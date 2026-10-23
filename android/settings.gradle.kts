// Gradle for Kurooto's Android app (0.7.0). android/build.sh runs it (a pinned Gradle it downloads and checks); see
// build.gradle.kts. The app is this one project: android/ itself, its sources in src/, res/, assets/.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "kurooto"
