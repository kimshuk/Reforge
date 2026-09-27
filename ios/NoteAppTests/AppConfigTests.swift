import Foundation
import XCTest
@testable import NoteApp

@MainActor
final class AppConfigTests: XCTestCase {
    func testDebugSimulatorFallsBackToLocalhost() throws {
        let config = try AppConfig.load(
            bundle: try makeBundle(),
            environment: [:],
            isDebug: true,
            isSimulator: true
        )

        XCTAssertEqual(config.backendBaseURL, "http://localhost:3000")
    }

    func testDebugDeviceRequiresInjectedLANOrHTTPSURL() throws {
        XCTAssertThrowsError(
            try AppConfig.load(
                bundle: try makeBundle(),
                environment: [:],
                isDebug: true,
                isSimulator: false
            )
        ) { error in
            XCTAssertEqual(error as? AppConfigError, .missingBackendBaseURL)
        }

        let config = try AppConfig.load(
            bundle: try makeBundle(),
            environment: ["NOTEAPP_BACKEND_BASE_URL": "http://192.168.0.10:3000"],
            isDebug: true,
            isSimulator: false
        )
        XCTAssertEqual(config.backendBaseURL, "http://192.168.0.10:3000")
    }

    func testReleaseRequiresInjectedHTTPSURL() throws {
        XCTAssertThrowsError(
            try AppConfig.load(
                bundle: try makeBundle(),
                environment: ["NOTEAPP_BACKEND_BASE_URL": "http://api.example.com"],
                isDebug: false,
                isSimulator: false
            )
        ) { error in
            XCTAssertEqual(error as? AppConfigError, .insecureBackendBaseURL)
        }

        let config = try AppConfig.load(
            bundle: try makeBundle(),
            environment: ["NOTEAPP_BACKEND_BASE_URL": "https://api.example.com"],
            isDebug: false,
            isSimulator: false
        )
        XCTAssertEqual(config.backendBaseURL, "https://api.example.com")
    }

    func testBundleValueIsUsedWhenEnvironmentIsAbsent() throws {
        let config = try AppConfig.load(
            bundle: try makeBundle(value: "https://bundle.example.com"),
            environment: [:],
            isDebug: false,
            isSimulator: false
        )

        XCTAssertEqual(config.backendBaseURL, "https://bundle.example.com")
    }

    func testRejectsBlankAndUnexpandedBuildSettingValues() throws {
        for value in ["", "   ", "$(NOTEAPP_BACKEND_BASE_URL)"] {
            XCTAssertThrowsError(
                try AppConfig.load(
                    bundle: try makeBundle(),
                    environment: ["NOTEAPP_BACKEND_BASE_URL": value],
                    isDebug: true,
                    isSimulator: true
                )
            ) { error in
                XCTAssertEqual(error as? AppConfigError, .invalidBackendBaseURL)
            }
        }
    }

    private func makeBundle(value: String? = nil) throws -> Bundle {
        let bundleURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("bundle")
        try FileManager.default.createDirectory(
            at: bundleURL,
            withIntermediateDirectories: true
        )
        var info: [String: Any] = [
            "CFBundleIdentifier": "com.andrewkim.noteapp.config-tests",
            "CFBundleName": "ConfigTests",
            "CFBundleVersion": "1",
        ]
        if let value {
            info["NOTEAPP_BACKEND_BASE_URL"] = value
        }
        let data = try PropertyListSerialization.data(
            fromPropertyList: info,
            format: .xml,
            options: 0
        )
        try data.write(to: bundleURL.appendingPathComponent("Info.plist"))
        return try XCTUnwrap(Bundle(url: bundleURL))
    }
}
