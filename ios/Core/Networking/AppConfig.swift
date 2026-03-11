import Foundation

struct AppConfig {
    let backendBaseURL: String

    static let `default`: AppConfig = {
        let envValue = ProcessInfo.processInfo.environment["NOTEAPP_BACKEND_BASE_URL"]
        if let envValue, !envValue.isEmpty {
            return AppConfig(backendBaseURL: envValue)
        }

        if let plistValue = Bundle.main.object(forInfoDictionaryKey: "NOTEAPP_BACKEND_BASE_URL") as? String,
           !plistValue.isEmpty {
            return AppConfig(backendBaseURL: plistValue)
        }

        return AppConfig(backendBaseURL: "http://localhost:3000")
    }()
}
