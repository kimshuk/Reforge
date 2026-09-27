import Foundation
import SwiftData

enum SharedModelContainerError: Error, Equatable {
    case appGroupUnavailable
}

enum SharedModelContainer {
    static let appGroupIdentifier = "group.com.andrewkim.noteapp"

    static func make(at storeURL: URL) throws -> ModelContainer {
        let schema = Schema([ContentNote.self, PendingNoteRoute.self])
        let configuration = ModelConfiguration(
            "ReforgeSharedContent",
            schema: schema,
            url: storeURL,
            allowsSave: true
        )
        return try ModelContainer(
            for: schema,
            configurations: [configuration]
        )
    }

    static func makeAppGroupContainer() throws -> ModelContainer {
        guard let directory = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: appGroupIdentifier
        ) else {
            throw SharedModelContainerError.appGroupUnavailable
        }
        return try make(at: directory.appendingPathComponent("reforge.sqlite"))
    }

    static func appGroupLock() throws -> SharedStoreLock {
        guard let directory = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: appGroupIdentifier
        ) else {
            throw SharedModelContainerError.appGroupUnavailable
        }
        return SharedStoreLock(
            fileURL: directory.appendingPathComponent("reforge-shared-store.lock")
        )
    }
}
