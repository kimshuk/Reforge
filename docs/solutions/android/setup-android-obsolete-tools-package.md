---
title: Override setup-android's obsolete tools package default
date: 2026-09-29
area: android
status: verified
---

## Problem

The first GitHub Actions run failed inside `android-actions/setup-android@v3` before Gradle started. Its SDK command ended with `Warning: Failed to find package 'tools'`.

## Mistake and why it failed

Using the action without inputs looked sufficient because the workflow installed the required API platform in the next step. However, the action's default `packages` value also requested the retired top-level SDK package `tools`, so setup failed before the explicit API 37 installation.

## Verified approach

`.github/workflows/ci.yml` sets `packages: platform-tools` on `android-actions/setup-android@v3`, then installs the exact `platforms;android-37.0` package separately. This preserves ADB while avoiding the unavailable legacy package. The workflow YAML parses successfully, and the preceding failure log identifies the removed default package as the failing command.

## Prevention

When changing Android SDK setup actions, inspect their implicit package list as well as explicit `sdkmanager` steps. Prefer exact current package IDs and override defaults that include retired SDK components.
