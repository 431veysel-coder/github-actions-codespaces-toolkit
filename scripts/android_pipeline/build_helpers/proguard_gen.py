#!/usr/bin/env python3
"""
ProGuard / R8 Rule Generator
Automatically generates -keep rules based on project analysis
"""

import json
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import get_config
from security_utils import SecurityError, validate_file_path


@dataclass
class KeepRule:
    """A ProGuard/R8 keep rule"""

    rule: str
    reason: str
    category: str  # reflection, serialization, jni, kotlin, androidx, third-party
    priority: int = 0  # Higher = more important


class ProGuardRuleGenerator:
    """Generate ProGuard/R8 rules from project analysis"""

    def __init__(self, project_path: str):
        self.project_path = Path(validate_file_path(project_path, must_exist=True))
        self.config = get_config()
        self.rules: List[KeepRule] = []

    def analyze_project(self) -> List[KeepRule]:
        """Analyze project and generate all necessary keep rules"""
        self.rules = []

        # 1. Reflection-based rules
        self.rules.extend(self._analyze_reflection())

        # 2. Serialization (Gson, Moshi, etc.)
        self.rules.extend(self._analyze_serialization())

        # 3. JNI / Native
        self.rules.extend(self._analyze_jni())

        # 4. Kotlin specific
        self.rules.extend(self._analyze_kotlin())

        # 5. AndroidX / Jetpack
        self.rules.extend(self._analyze_androidx())

        # 6. Third-party libraries
        self.rules.extend(self._analyze_third_party())

        # 7. Room Database
        self.rules.extend(self._analyze_room())

        # 8. WorkManager / Services
        self.rules.extend(self._analyze_workmanager())

        # 9. Dagger/Hilt/Koin DI
        self.rules.extend(self._analyze_di())

        # 10. Retrofit/OkHttp
        self.rules.extend(self._analyze_network())

        return self.rules

    def _analyze_reflection(self) -> List[KeepRule]:
        """Find reflection usage and generate rules"""
        rules = []

        kotlin_files = list(self.project_path.rglob("*.kt"))
        java_files = list(self.project_path.rglob("*.java"))

        for file in kotlin_files + java_files:
            try:
                content = file.read_text(encoding="utf-8")

                # Class.forName
                for match in re.finditer(r'Class\.forName\s*\(\s*["\']([^"\']+)["\']', content):
                    class_name = match.group(1)
                    rules.append(
                        KeepRule(
                            rule=f"-keep class {class_name} {{ *; }}",
                            reason=f'Class.forName("{class_name}") in {file.name}',
                            category="reflection",
                            priority=10,
                        )
                    )

                # ::class.java / .class
                for match in re.finditer(r"(\w+(?:\.\w+)*)::class\.java", content):
                    class_name = match.group(1).replace(".", "/")
                    rules.append(
                        KeepRule(
                            rule=f"-keep class {class_name} {{ *; }}",
                            reason=f"Kotlin class literal {match.group(1)} in {file.name}",
                            category="reflection",
                            priority=8,
                        )
                    )

                # .javaClass / .class
                for match in re.finditer(r"(\w+(?:\.\w+)*)\.javaClass", content):
                    class_name = match.group(1).replace(".", "/")
                    rules.append(
                        KeepRule(
                            rule=f"-keep class {class_name} {{ *; }}",
                            reason=f"javaClass reference in {file.name}",
                            category="reflection",
                            priority=8,
                        )
                    )

                # Method references that might be used reflectively
                for match in re.finditer(r"::(\w+)", content):
                    method = match.group(1)
                    if method[0].isupper():  # Likely class name
                        rules.append(
                            KeepRule(
                                rule=f"-keepclassmembers class * {{ public * {method}(...); }}",
                                reason=f"Possible method reference ::{method} in {file.name}",
                                category="reflection",
                                priority=5,
                            )
                        )

                # Annotations that trigger reflection
                reflection_annotations = [
                    "@JsonProperty",
                    "@SerializedName",
                    "@Expose",
                    "@Parcelize",
                    "@Entity",
                    "@Database",
                    "@Dao",
                    "@Query",
                    "@Insert",
                    "@Update",
                    "@Delete",
                    "@Inject",
                    "@Provides",
                    "@Module",
                    "@Component",
                    "@HiltAndroidApp",
                    "@AndroidEntryPoint",
                    "@Route",
                    "@Destination",
                    "@AutoRoute",
                    "@BindView",
                    "@OnClick",
                    "@OnLongClick",
                ]
                for ann in reflection_annotations:
                    if ann in content:
                        # Extract annotated class
                        class_match = re.search(
                            rf"{re.escape(ann)}\s*\n\s*(?:class|data class|object)\s+(\w+)", content
                        )
                        if class_match:
                            class_name = class_match.group(1)
                            rules.append(
                                KeepRule(
                                    rule=f"-keep class * extends {class_name} {{ *; }}",
                                    reason=f"{ann} annotation on {class_name}",
                                    category="reflection",
                                    priority=9,
                                )
                            )
            except Exception:
                pass

        return rules

    def _analyze_serialization(self) -> List[KeepRule]:
        """Generate rules for JSON serialization libraries"""
        rules = []

        # Check for Gson
        if self._has_dependency("com.google.code.gson:gson"):
            rules.append(
                KeepRule(
                    rule="-keepattributes Signature",
                    reason="Gson requires Signature attribute for generic types",
                    category="serialization",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class com.google.gson.** { *; }",
                    reason="Keep Gson internals",
                    category="serialization",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements com.google.gson.TypeAdapter",
                    reason="Custom TypeAdapters",
                    category="serialization",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements com.google.gson.JsonSerializer",
                    reason="Custom JsonSerializers",
                    category="serialization",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements com.google.gson.JsonDeserializer",
                    reason="Custom JsonDeserializers",
                    category="serialization",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @com.google.gson.annotations.SerializedName <fields>; }",
                    reason="Gson @SerializedName fields",
                    category="serialization",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @com.google.gson.annotations.Expose <fields>; }",
                    reason="Gson @Expose fields",
                    category="serialization",
                    priority=9,
                )
            )

        # Check for Moshi
        if self._has_dependency("com.squareup.moshi:moshi"):
            rules.append(
                KeepRule(
                    rule="-keep class com.squareup.moshi.** { *; }",
                    reason="Keep Moshi internals",
                    category="serialization",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements com.squareup.moshi.JsonAdapter",
                    reason="Custom Moshi JsonAdapters",
                    category="serialization",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @com.squareup.moshi.Json <fields>; }",
                    reason="Moshi @Json fields",
                    category="serialization",
                    priority=10,
                )
            )

        # Check for Kotlinx Serialization
        if self._has_dependency("org.jetbrains.kotlinx:kotlinx-serialization"):
            rules.append(
                KeepRule(
                    rule="-keep class kotlinx.serialization.** { *; }",
                    reason="Keep Kotlinx Serialization internals",
                    category="serialization",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @kotlinx.serialization.Serializable class * { *; }",
                    reason="Keep @Serializable classes",
                    category="serialization",
                    priority=10,
                )
            )

        # Parcelize
        if self._has_dependency("org.jetbrains.kotlin:kotlin-parcelize"):
            rules.append(
                KeepRule(
                    rule="-keep @kotlin.parcelize.Parcelize class * { *; }",
                    reason="Kotlin @Parcelize classes",
                    category="serialization",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * implements android.os.Parcelable { *; }",
                    reason="Parcelable implementation",
                    category="serialization",
                    priority=10,
                )
            )

        return rules

    def _analyze_jni(self) -> List[KeepRule]:
        """Generate rules for JNI native methods"""
        rules = []

        # Check for native methods in Java/Kotlin
        jni_classes = set()

        for file in self.project_path.rglob("*.kt"):
            try:
                content = file.read_text()
                # external fun
                for match in re.finditer(r"(?:external|native)\s+fun\s+(\w+)", content):
                    # Find class name
                    class_match = re.search(r"(?:class|data class|object)\s+(\w+)", content)
                    if class_match:
                        jni_classes.add(class_match.group(1))
            except Exception:
                pass

        for file in self.project_path.rglob("*.java"):
            try:
                content = file.read_text()
                # native method
                for match in re.finditer(r"native\s+(?:static\s+)?\w+\s+(\w+)", content):
                    # Find class name
                    class_match = re.search(r"class\s+(\w+)", content)
                    if class_match:
                        jni_classes.add(class_match.group(1))
            except Exception:
                pass

        # Check CMakeLists.txt for JNI
        cmake_files = list(self.project_path.rglob("CMakeLists.txt"))
        for cmake in cmake_files:
            try:
                content = cmake.read_text()
                # Find JNI function names
                for match in re.finditer(r"Java_([^_]+)_(\w+)", content):
                    # Class name from JNI convention
                    pass
            except Exception:
                pass

        for cls in jni_classes:
            rules.append(
                KeepRule(
                    rule=f"-keep class {cls} {{ native <methods>; }}",
                    reason=f"JNI native methods in {cls}",
                    category="jni",
                    priority=10,
                )
            )

        # General JNI rules
        rules.append(
            KeepRule(
                rule="-keepclasseswithmembernames class * { native <methods>; }",
                reason="All native methods",
                category="jni",
                priority=10,
            )
        )

        return rules

    def _analyze_kotlin(self) -> List[KeepRule]:
        """Kotlin-specific rules"""
        rules = []

        # Inline classes (value classes)
        rules.append(
            KeepRule(
                rule="-keep @kotlin.internal.ValueClass class * { *; }",
                reason="Kotlin value classes",
                category="kotlin",
                priority=8,
            )
        )

        # Sealed classes
        rules.append(
            KeepRule(
                rule="-keep @kotlin.Sealed class * { *; }",
                reason="Kotlin sealed classes",
                category="kotlin",
                priority=8,
            )
        )

        # Data classes (often used for serialization)
        rules.append(
            KeepRule(
                rule="-keep @kotlin.Metadata class * { *; }", reason="Kotlin metadata", category="kotlin", priority=7
            )
        )

        # Coroutines
        if self._has_dependency("org.jetbrains.kotlinx:kotlinx-coroutines"):
            rules.append(
                KeepRule(
                    rule="-keep class kotlinx.coroutines.** { *; }",
                    reason="Kotlinx Coroutines",
                    category="kotlin",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @kotlinx.coroutines.* *; }",
                    reason="Coroutines annotations",
                    category="kotlin",
                    priority=8,
                )
            )

        # Flow
        if self._has_dependency("org.jetbrains.kotlinx:kotlinx-coroutines-core"):
            rules.append(
                KeepRule(
                    rule="-keep class kotlinx.coroutines.flow.** { *; }",
                    reason="Kotlin Flow",
                    category="kotlin",
                    priority=8,
                )
            )

        return rules

    def _analyze_androidx(self) -> List[KeepRule]:
        """AndroidX / Jetpack library rules"""
        rules = []

        # Lifecycle / ViewModel
        if self._has_dependency("androidx.lifecycle:lifecycle-viewmodel"):
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.lifecycle.ViewModel { *; }",
                    reason="ViewModel subclasses",
                    category="androidx",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements androidx.lifecycle.ViewModelProvider.Factory { *; }",
                    reason="ViewModelFactory implementations",
                    category="androidx",
                    priority=9,
                )
            )

        if self._has_dependency("androidx.lifecycle:lifecycle-livedata"):
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.lifecycle.LiveData { *; }",
                    reason="LiveData subclasses",
                    category="androidx",
                    priority=9,
                )
            )

        # Room
        if self._has_dependency("androidx.room:room-runtime"):
            rules.append(
                KeepRule(
                    rule="-keep @androidx.room.Entity class * { *; }",
                    reason="Room @Entity classes",
                    category="androidx",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @androidx.room.Dao class * { *; }",
                    reason="Room @Dao interfaces",
                    category="androidx",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.room.RoomDatabase { *; }",
                    reason="RoomDatabase subclasses",
                    category="androidx",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class androidx.room.** { *; }", reason="Room internals", category="androidx", priority=8
                )
            )

        # Navigation
        if self._has_dependency("androidx.navigation:navigation-fragment"):
            rules.append(
                KeepRule(
                    rule="-keep @androidx.navigation.NavDestination class * { *; }",
                    reason="Navigation destinations",
                    category="androidx",
                    priority=9,
                )
            )

        # WorkManager
        if self._has_dependency("androidx.work:work-runtime"):
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.work.Worker { *; }",
                    reason="Worker subclasses",
                    category="androidx",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.work.ListenableWorker { *; }",
                    reason="ListenableWorker subclasses",
                    category="androidx",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class androidx.work.** { *; }",
                    reason="WorkManager internals",
                    category="androidx",
                    priority=8,
                )
            )

        # Paging
        if self._has_dependency("androidx.paging:paging-runtime"):
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.paging.PagingSource { *; }",
                    reason="PagingSource implementations",
                    category="androidx",
                    priority=9,
                )
            )

        # DataStore
        if self._has_dependency("androidx.datastore:datastore-preferences"):
            rules.append(
                KeepRule(
                    rule="-keep class androidx.datastore.** { *; }",
                    reason="DataStore internals",
                    category="androidx",
                    priority=8,
                )
            )

        # Benchmark
        if self._has_dependency("androidx.benchmark:benchmark-junit4"):
            rules.append(
                KeepRule(
                    rule="-keep class androidx.benchmark.** { *; }",
                    reason="Benchmark internals",
                    category="androidx",
                    priority=7,
                )
            )

        return rules

    def _analyze_third_party(self) -> List[KeepRule]:
        """Third-party library rules"""
        rules = []

        # Retrofit / OkHttp
        if self._has_dependency("com.squareup.retrofit2:retrofit"):
            rules.append(
                KeepRule(
                    rule="-keep class retrofit2.** { *; }",
                    reason="Retrofit internals",
                    category="third-party",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements retrofit2.Call { *; }",
                    reason="Retrofit Call interfaces",
                    category="third-party",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @retrofit2.http.* <methods>; }",
                    reason="Retrofit HTTP annotations",
                    category="third-party",
                    priority=10,
                )
            )

        if self._has_dependency("com.squareup.okhttp3:okhttp"):
            rules.append(
                KeepRule(
                    rule="-keep class okhttp3.** { *; }", reason="OkHttp internals", category="third-party", priority=8
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @okhttp3.* *; }",
                    reason="OkHttp annotations",
                    category="third-party",
                    priority=9,
                )
            )

        # Glide / Coil / Picasso
        if self._has_dependency("com.github.bumptech.glide:glide"):
            rules.append(
                KeepRule(
                    rule="-keep class com.bumptech.glide.** { *; }",
                    reason="Glide internals",
                    category="third-party",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements com.bumptech.glide.module.AppGlideModule { *; }",
                    reason="Glide modules",
                    category="third-party",
                    priority=9,
                )
            )

        if self._has_dependency("io.coil-kt:coil"):
            rules.append(
                KeepRule(rule="-keep class coil.** { *; }", reason="Coil internals", category="third-party", priority=8)
            )

        # Firebase
        if self._has_dependency("com.google.firebase:firebase-messaging"):
            rules.append(
                KeepRule(
                    rule="-keep class com.google.firebase.** { *; }",
                    reason="Firebase internals",
                    category="third-party",
                    priority=8,
                )
            )

        # Crashlytics
        if self._has_dependency("com.google.firebase:firebase-crashlytics"):
            rules.append(
                KeepRule(
                    rule="-keep class com.google.firebase.crashlytics.** { *; }",
                    reason="Crashlytics internals",
                    category="third-party",
                    priority=8,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepattributes SourceFile,LineNumberTable",
                    reason="Crashlytics needs source info",
                    category="third-party",
                    priority=10,
                )
            )

        # Analytics
        if self._has_dependency("com.google.firebase:firebase-analytics"):
            rules.append(
                KeepRule(
                    rule="-keep class com.google.firebase.analytics.** { *; }",
                    reason="Firebase Analytics",
                    category="third-party",
                    priority=8,
                )
            )

        # Advertising ID
        if self._has_dependency("com.google.android.gms:play-services-ads-identifier"):
            rules.append(
                KeepRule(
                    rule="-keep class com.google.android.gms.ads.identifier.** { *; }",
                    reason="Advertising ID",
                    category="third-party",
                    priority=8,
                )
            )

        return rules

    def _analyze_room(self) -> List[KeepRule]:
        """Room database specific rules"""
        rules = []

        if self._has_dependency("androidx.room:room-runtime"):
            rules.append(
                KeepRule(
                    rule="-keep @androidx.room.Entity class * { *; }",
                    reason="Room @Entity classes",
                    category="room",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @androidx.room.Dao class * { *; }",
                    reason="Room @Dao interfaces",
                    category="room",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.room.RoomDatabase { *; }",
                    reason="RoomDatabase subclasses",
                    category="room",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class androidx.room.** { *; }", reason="Room internals", category="room", priority=8
                )
            )
            # Type converters
            rules.append(
                KeepRule(
                    rule="-keep class * { @androidx.room.TypeConverters <fields>; }",
                    reason="Room @TypeConverters",
                    category="room",
                    priority=9,
                )
            )

        return rules

    def _analyze_workmanager(self) -> List[KeepRule]:
        """WorkManager rules"""
        rules = []

        if self._has_dependency("androidx.work:work-runtime"):
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.work.Worker { *; }",
                    reason="Worker subclasses",
                    category="workmanager",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.work.ListenableWorker { *; }",
                    reason="ListenableWorker subclasses",
                    category="workmanager",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.work.CoroutineWorker { *; }",
                    reason="CoroutineWorker subclasses",
                    category="workmanager",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * extends androidx.work.RxWorker { *; }",
                    reason="RxWorker subclasses",
                    category="workmanager",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class androidx.work.** { *; }",
                    reason="WorkManager internals",
                    category="workmanager",
                    priority=8,
                )
            )

        return rules

    def _analyze_di(self) -> List[KeepRule]:
        """Dependency Injection rules"""
        rules = []

        # Dagger / Hilt
        if self._has_dependency("com.google.dagger:hilt-android"):
            rules.append(
                KeepRule(
                    rule="-keep @dagger.hilt.android.HiltAndroidApp class * { *; }",
                    reason="Hilt application class",
                    category="di",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @dagger.hilt.android.AndroidEntryPoint class * { *; }",
                    reason="Hilt entry points",
                    category="di",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @dagger.Module class * { *; }", reason="Dagger modules", category="di", priority=10
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @dagger.hilt.InstallIn class * { *; }",
                    reason="Hilt components",
                    category="di",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep @javax.inject.Qualifier class * { *; }",
                    reason="Qualifier annotations",
                    category="di",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(rule="-keep class dagger.** { *; }", reason="Dagger internals", category="di", priority=8)
            )
            rules.append(
                KeepRule(rule="-keep class dagger.hilt.** { *; }", reason="Hilt internals", category="di", priority=8)
            )

        # Koin
        if self._has_dependency("org.koin:koin-android"):
            rules.append(
                KeepRule(rule="-keep class org.koin.** { *; }", reason="Koin internals", category="di", priority=8)
            )
            rules.append(
                KeepRule(
                    rule="-keep class * { @org.koin.dsl.ModuleDefinition *; }",
                    reason="Koin modules",
                    category="di",
                    priority=9,
                )
            )

        return rules

    def _analyze_network(self) -> List[KeepRule]:
        """Network/Retrofit rules"""
        rules = []

        if self._has_dependency("com.squareup.retrofit2:retrofit"):
            rules.append(
                KeepRule(
                    rule="-keep class retrofit2.** { *; }", reason="Retrofit internals", category="network", priority=8
                )
            )
            rules.append(
                KeepRule(
                    rule="-keep class * implements retrofit2.Call { *; }",
                    reason="Retrofit Call interfaces",
                    category="network",
                    priority=9,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @retrofit2.http.* <methods>; }",
                    reason="Retrofit HTTP annotations",
                    category="network",
                    priority=10,
                )
            )
            rules.append(
                KeepRule(
                    rule="-keepclassmembers class * { @retrofit2.http.* <fields>; }",
                    reason="Retrofit HTTP field annotations",
                    category="network",
                    priority=9,
                )
            )

        if self._has_dependency("com.squareup.okhttp3:okhttp"):
            rules.append(
                KeepRule(
                    rule="-keep class okhttp3.** { *; }", reason="OkHttp internals", category="network", priority=8
                )
            )

        return rules

    def _has_dependency(self, dependency: str) -> bool:
        """Check if project has a dependency"""
        # Check Gradle files
        gradle_files = list(self.project_path.rglob("build.gradle*"))
        for gf in gradle_files:
            try:
                content = gf.read_text()
                if dependency in content:
                    return True
            except Exception:
                pass

        # Check Maven
        pom_files = list(self.project_path.rglob("pom.xml"))
        for pom in pom_files:
            try:
                content = pom.read_text()
                if dependency in content:
                    return True
            except Exception:
                pass

        return False

    def generate_rules_file(self, output_path: str = None) -> str:
        """Generate proguard-rules.pro file"""
        self.analyze_project()

        # Sort by priority (highest first)
        self.rules.sort(key=lambda r: -r.priority)

        # Group by category
        by_category = defaultdict(list)
        for rule in self.rules:
            by_category[rule.category].append(rule)

        # Generate content
        lines = [
            "# Auto-generated ProGuard/R8 rules by Minis ProGuard Generator",
            "# Project: " + str(self.project_path),
            "# Generated: " + subprocess.run(["date"], capture_output=True, text=True).stdout.strip(),
            "",
        ]

        # Standard rules first
        lines.extend(
            [
                "# ==================== STANDARD RULES ====================",
                "-dontwarn android.**",
                "-dontwarn androidx.**",
                "-dontwarn com.google.android.**",
                "-dontwarn kotlin.**",
                "-dontwarn kotlinx.**",
                "-dontwarn org.jetbrains.**",
                "",
                "-keepattributes SourceFile,LineNumberTable",
                "-keepattributes *Annotation*",
                "-keepattributes Signature",
                "-keepattributes EnclosingMethod",
                "-keepattributes InnerClasses",
                "",
            ]
        )

        # Category rules
        category_order = [
            "reflection",
            "serialization",
            "jni",
            "kotlin",
            "androidx",
            "room",
            "workmanager",
            "di",
            "network",
            "third-party",
        ]

        for cat in category_order:
            if cat in by_category:
                lines.append(f"# ==================== {cat.upper()} ====================")
                for rule in by_category[cat]:
                    lines.append(f"# {rule.reason}")
                    lines.append(rule.rule)
                lines.append("")

        # Any remaining categories
        for cat, rules in by_category.items():
            if cat not in category_order:
                lines.append(f"# ==================== {cat.upper()} ====================")
                for rule in rules:
                    lines.append(f"# {rule.reason}")
                    lines.append(rule.rule)
                lines.append("")

        # Optimization rules
        lines.extend(
            [
                "# ==================== OPTIMIZATION ====================",
                "-optimizations !code/simplification/arithmetic,!field/*,!class/merging/*",
                "-optimizationpasses 5",
                "",
                "# ==================== KEEP ENTRY POINTS ====================",
                "-keep public class * extends android.app.Application { *; }",
                "-keep public class * extends android.app.Activity { *; }",
                "-keep public class * extends android.app.Service { *; }",
                "-keep public class * extends android.content.BroadcastReceiver { *; }",
                "-keep public class * extends android.content.ContentProvider { *; }",
                "-keep public class * extends android.view.View { *; }",
                "-keep public class * extends android.app.Fragment { *; }",
                "-keep public class * extends androidx.fragment.app.Fragment { *; }",
                "",
            ]
        )

        content = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(content)

        return content

    def get_rules_summary(self) -> Dict[str, Any]:
        """Get summary of generated rules"""
        self.analyze_project()

        by_category = defaultdict(list)
        for rule in self.rules:
            by_category[rule.category].append({"rule": rule.rule, "reason": rule.reason, "priority": rule.priority})

        return {
            "total_rules": len(self.rules),
            "by_category": {cat: len(rules) for cat, rules in by_category.items()},
            "categories": dict(by_category),
        }


# Standalone functions for MCP tool integration
def generate_proguard_rules(project_path: str, output_path: str = None) -> Dict[str, Any]:
    """MCP tool: Generate ProGuard/R8 rules"""
    try:
        generator = ProGuardRuleGenerator(project_path)
        content = generator.generate_rules_file(output_path)
        summary = generator.get_rules_summary()
        return {"success": True, "content": content, "summary": summary, "output_path": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_proguard_needs(project_path: str) -> Dict[str, Any]:
    """MCP tool: Analyze what ProGuard rules are needed"""
    try:
        generator = ProGuardRuleGenerator(project_path)
        generator.analyze_project()
        return generator.get_rules_summary()
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "."
    output = sys.argv[2] if len(sys.argv) > 2 else None

    generator = ProGuardRuleGenerator(project)
    content = generator.generate_rules_file(output)

    if output:
        print(f"Rules written to {output}")
    else:
        print(content)
