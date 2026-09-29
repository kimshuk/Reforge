---
title: Align AGP built-in Kotlin with Coil's compiled metadata
date: 2026-09-29
area: android
status: verified
---

## Problem

The first Android Debug build failed in `:app:compileDebugKotlin`: AGP 9.4's default built-in Kotlin compiler was 2.2.10, while Coil 3.6.3 brought `kotlin-stdlib:2.4.10` onto the app classpath. The compiler could read metadata only through 2.3.0.

## Mistake and why it failed

Pinning the Compose and Serialization plugins to 2.2.10 seemed to match AGP's built-in Kotlin version, but it did not account for Kotlin metadata in the pinned Coil dependency. `:app:dependencyInsight --configuration debugCompileClasspath --dependency kotlin-stdlib` traced the 2.4.10 selection to Coil 3.6.3. Removing Coil made the scaffold compile, but it would leave the planned image dependency unverified.

## Verified approach

`android/build.gradle.kts` adds `org.jetbrains.kotlin:kotlin-gradle-plugin:2.4.10` to the top-level buildscript classpath while retaining AGP built-in Kotlin. `android/gradle/libs.versions.toml` pins the Compose and Serialization compiler plugins to 2.4.10, and `android/app/build.gradle.kts` includes Coil 3.6.3. The Debug unit test, APK, and lint tasks passed together. The test-only Room processor fixture in `android/app/src/test/java/com/andrewkim/reforge/config/RoomProcessorSmokeTest.kt` also proved that KSP 2.3.10 generated `ProcessorSmokeDatabase_Impl`.

## Prevention

When adding Kotlin libraries to this AGP 9 project, compare their resolved Kotlin standard library and metadata requirements with the built-in compiler before assuming the AGP default is sufficient. Verify the actual compile task and KSP-generated output, not just Gradle configuration. For Android unit-test processors, KSP's variant configuration is `kspTestDebug`.
