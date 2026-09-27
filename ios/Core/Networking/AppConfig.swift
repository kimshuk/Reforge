import Foundation

enum AppConfigError: Error, Equatable {
    case missingBackendBaseURL
    case invalidBackendBaseURL
    case insecureBackendBaseURL
}

struct AppConfig {
    let backendBaseURL: String

    static let `default`: AppConfig = {
        #if DEBUG
        let isDebug = true
        #else
        let isDebug = false
        #endif

        #if targetEnvironment(simulator)
        let isSimulator = true
        #else
        let isSimulator = false
        #endif

        do {
            return try load(
                bundle: .main,
                environment: ProcessInfo.processInfo.environment,
                isDebug: isDebug,
                isSimulator: isSimulator
            )
        } catch {
            fatalError("Invalid backend configuration: \(error)")
        }
    }()

    static func load(
        bundle: Bundle,
        environment: [String: String],
        isDebug: Bool,
        isSimulator: Bool
    ) throws -> AppConfig {
        let key = "NOTEAPP_BACKEND_BASE_URL"
        let environmentValue = environment[key]
        let bundleValue = bundle.object(forInfoDictionaryKey: key) as? String

        let rawValue: String?
        if let environmentValue {
            rawValue = environmentValue
        } else if let bundleValue,
                  !bundleValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            rawValue = bundleValue
        } else {
            rawValue = nil
        }

        guard let rawValue else {
            if isDebug && isSimulator {
                return AppConfig(backendBaseURL: "http://localhost:3000")
            }
            throw AppConfigError.missingBackendBaseURL
        }

        let value = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard
            !value.isEmpty,
            !value.contains("$("),
            let url = URL(string: value),
            let scheme = url.scheme?.lowercased(),
            scheme == "http" || scheme == "https",
            url.host != nil
        else {
            throw AppConfigError.invalidBackendBaseURL
        }

        if !isDebug && scheme != "https" {
            throw AppConfigError.insecureBackendBaseURL
        }

        if isDebug && !isSimulator && scheme == "http" {
            let host = url.host?.lowercased()
            if host == "localhost" || host == "127.0.0.1" || host == "::1" {
                throw AppConfigError.invalidBackendBaseURL
            }
        }

        return AppConfig(backendBaseURL: value)
    }
}
