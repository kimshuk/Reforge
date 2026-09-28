import SwiftData
import XCTest
@testable import NoteApp

@MainActor
final class ContentNoteRepositoryTests: XCTestCase {
    func testSavingNewDraftCreatesOneNoteAndOneRoute() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }

        let draft = makeDraft()
        let outcome = try fixture.repository.saveOrReuse(draft)

        guard case let .saved(stored) = outcome else {
            return XCTFail("Expected a newly saved note")
        }
        XCTAssertEqual(stored.id, draft.id)

        let context = ModelContext(fixture.container)
        let notes = try context.fetch(FetchDescriptor<ContentNote>())
        let routes = try context.fetch(FetchDescriptor<PendingNoteRoute>())
        XCTAssertEqual(notes.count, 1)
        XCTAssertEqual(routes.count, 1)
        XCTAssertEqual(routes.first?.noteId, notes.first?.id)
    }

    func testReusingExistingNotePreservesOriginalFieldsAndAddsRoute() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }

        let original = makeDraft()
        _ = try fixture.repository.saveOrReuse(original)
        let changed = makeDraft(
            id: UUID(),
            sourceURL: URL(string: "https://www.youtube.com/shorts/dQw4w9WgXcQ")!,
            title: "Changed title",
            transcriptText: "Changed transcript",
            createdAt: Date(timeIntervalSince1970: 2_000)
        )

        let outcome = try fixture.repository.saveOrReuse(changed)

        guard case let .alreadySaved(stored) = outcome else {
            return XCTFail("Expected the original note to be reused")
        }
        assertStored(stored, equals: original)
        let context = ModelContext(fixture.container)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<ContentNote>()), 1)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 2)
    }

    func testConcurrentContainersKeepOneNoteAndTwoRoutes() async throws {
        let directory = try makeDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let storeURL = directory.appendingPathComponent("store.sqlite")
        let lockURL = directory.appendingPathComponent("reforge-shared-store.lock")
        let firstContainer = try SharedModelContainer.make(at: storeURL)
        let secondContainer = try SharedModelContainer.make(at: storeURL)
        let firstRepository = ContentNoteRepository(
            container: firstContainer,
            lock: SharedStoreLock(fileURL: lockURL)
        )
        let secondRepository = ContentNoteRepository(
            container: secondContainer,
            lock: SharedStoreLock(fileURL: lockURL)
        )
        let firstDraft = makeDraft()
        let secondDraft = makeDraft(
            id: UUID(),
            sourceURL: URL(string: "https://www.youtube.com/shorts/dQw4w9WgXcQ")!,
            title: "Concurrent title",
            transcriptText: "Concurrent transcript",
            createdAt: Date(timeIntervalSince1970: 2_000)
        )

        let firstTask = Task.detached {
            try firstRepository.saveOrReuse(firstDraft)
        }
        let secondTask = Task.detached {
            try secondRepository.saveOrReuse(secondDraft)
        }
        let outcomes = try await [firstTask.value, secondTask.value]

        let saved = try XCTUnwrap(outcomes.compactMap { outcome -> StoredContentNote? in
            guard case let .saved(note) = outcome else { return nil }
            return note
        }.first)
        XCTAssertEqual(outcomes.filter {
            if case .alreadySaved = $0 { return true }
            return false
        }.count, 1)

        let verificationContainer = try SharedModelContainer.make(at: storeURL)
        let context = ModelContext(verificationContainer)
        let notes = try context.fetch(FetchDescriptor<ContentNote>())
        XCTAssertEqual(notes.count, 1)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 2)
        XCTAssertEqual(notes.first?.stored, saved)
    }

    func testSnapshotAcknowledgeOnlyDeletesCapturedRoutes() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        _ = try fixture.repository.saveOrReuse(draft)
        let firstSnapshot = try fixture.repository.pendingRouteSnapshot()
        XCTAssertEqual(firstSnapshot.noteID, draft.id)

        let recreated = ContentNoteRepository(
            container: try SharedModelContainer.make(
                at: fixture.directory.appendingPathComponent("store.sqlite")
            ),
            lock: SharedStoreLock(
                fileURL: fixture.directory.appendingPathComponent("reforge-shared-store.lock")
            )
        )
        XCTAssertEqual(try recreated.pendingRouteSnapshot(), firstSnapshot)

        try recreated.enqueueRoute(noteID: draft.id)
        try fixture.repository.acknowledge(routeIDs: firstSnapshot.routeIDs)

        let remaining = try recreated.pendingRouteSnapshot()
        XCTAssertEqual(remaining.routeIDs.count, 1)
        XCTAssertEqual(remaining.noteID, draft.id)
    }

    func testSnapshotReturnsNilForLatestMissingNoteAndCanAcknowledgeIt() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        try fixture.repository.enqueueRoute(noteID: UUID())

        let snapshot = try fixture.repository.pendingRouteSnapshot()

        XCTAssertNil(snapshot.noteID)
        XCTAssertEqual(snapshot.routeIDs.count, 1)
        try fixture.repository.acknowledge(routeIDs: snapshot.routeIDs)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
    }

    func testSnapshotOrdersRoutesByCreationAndRejectsLatestTrashedNote() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let active = makeDraft(id: UUID())
        let trashed = makeDraft(id: UUID())
        let firstRoute = PendingNoteRoute(
            noteId: active.id, createdAt: Date(timeIntervalSince1970: 100)
        )
        let latestRoute = PendingNoteRoute(
            noteId: trashed.id, createdAt: Date(timeIntervalSince1970: 200)
        )
        let context = ModelContext(fixture.container)
        let activeModel = ContentNote(draft: active)
        let trashedModel = ContentNote(draft: trashed)
        trashedModel.sourceKey = trashed.id.uuidString
        trashedModel.trashedAt = Date(timeIntervalSince1970: 300)
        context.insert(activeModel)
        context.insert(trashedModel)
        context.insert(latestRoute)
        context.insert(firstRoute)
        try context.save()

        let snapshot = try fixture.repository.pendingRouteSnapshot()

        XCTAssertEqual(snapshot.routeIDs, [firstRoute.id, latestRoute.id])
        XCTAssertNil(snapshot.noteID)
        try fixture.repository.acknowledge(routeIDs: [latestRoute.id])
        XCTAssertEqual(try fixture.repository.pendingRouteSnapshot().noteID, active.id)
    }

    func testActiveAndTrashedNotesSortNewestFirst() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let older = makeDraft(id: UUID(), createdAt: Date(timeIntervalSince1970: 100))
        let newer = makeDraft(id: UUID(), createdAt: Date(timeIntervalSince1970: 200))
        let middleActive = makeDraft(id: UUID(), createdAt: Date(timeIntervalSince1970: 250))
        let other = makeDraft(id: UUID(), createdAt: Date(timeIntervalSince1970: 300))
        for draft in [older, newer, middleActive, other] {
            let context = ModelContext(fixture.container)
            let note = ContentNote(draft: draft)
            note.sourceKey = draft.id.uuidString
            context.insert(note)
            try context.save()
        }
        try fixture.repository.moveToTrash(noteID: older.id, at: Date(timeIntervalSince1970: 400))
        try fixture.repository.moveToTrash(noteID: newer.id, at: Date(timeIntervalSince1970: 500))

        XCTAssertEqual(try fixture.repository.activeNotes().map(\.id), [other.id, middleActive.id])
        XCTAssertEqual(try fixture.repository.trashedNotes().map(\.id), [newer.id, older.id])
    }

    func testMoveRestoreAndPermanentDeletePreserveFieldsAndRemoveRoutes() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        _ = try fixture.repository.saveOrReuse(draft)
        try fixture.repository.enqueueRoute(noteID: draft.id)
        let deletedAt = Date(timeIntervalSince1970: 2_000)

        try fixture.repository.moveToTrash(noteID: draft.id, at: deletedAt)
        XCTAssertEqual(try fixture.repository.note(id: draft.id)?.trashedAt, deletedAt)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
        XCTAssertTrue(try fixture.repository.activeNotes().isEmpty)

        try fixture.repository.restore(noteID: draft.id)
        let restored = try XCTUnwrap(fixture.repository.note(id: draft.id))
        assertStored(restored, equals: draft)
        XCTAssertNil(restored.trashedAt)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)

        try fixture.repository.enqueueRoute(noteID: draft.id)
        try fixture.repository.deletePermanently(noteID: draft.id)
        XCTAssertNil(try fixture.repository.note(id: draft.id))
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
    }

    func testRestoreAndEnqueueRouteAndTrashedReuse() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        _ = try fixture.repository.saveOrReuse(draft)
        try fixture.repository.moveToTrash(noteID: draft.id, at: Date(timeIntervalSince1970: 2_000))

        let result = try fixture.repository.saveOrReuse(makeDraft(id: UUID(), title: "Replacement"))
        guard case let .restoreRequired(note) = result else {
            return XCTFail("Expected restore confirmation")
        }
        XCTAssertEqual(note.id, draft.id)
        XCTAssertEqual(note.title, draft.title)
        XCTAssertEqual(try fixture.repository.trashedNotes().count, 1)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)

        let restored = try fixture.repository.restoreAndEnqueueRoute(noteID: draft.id)
        assertStored(restored, equals: draft)
        XCTAssertNil(restored.trashedAt)
        XCTAssertEqual(try fixture.repository.pendingRouteSnapshot().noteID, draft.id)
    }

    func testRestoreAndEnqueueRouteSaveFailureLeavesTrashedNoteAndNoRoute() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        let trashedAt = Date(timeIntervalSince1970: 2_000)
        _ = try fixture.repository.saveOrReuse(draft)
        try fixture.repository.moveToTrash(noteID: draft.id, at: trashedAt)

        let schema = Schema([ContentNote.self, PendingNoteRoute.self])
        let readOnlyConfiguration = ModelConfiguration(
            "ReforgeSharedContent",
            schema: schema,
            url: fixture.directory.appendingPathComponent("store.sqlite"),
            allowsSave: false
        )
        let readOnlyContainer = try ModelContainer(
            for: schema,
            configurations: [readOnlyConfiguration]
        )
        let readOnlyRepository = ContentNoteRepository(
            container: readOnlyContainer,
            lock: SharedStoreLock(fileURL: fixture.directory.appendingPathComponent("reforge-shared-store.lock"))
        )

        XCTAssertThrowsError(try readOnlyRepository.restoreAndEnqueueRoute(noteID: draft.id))

        let reopened = try SharedModelContainer.make(
            at: fixture.directory.appendingPathComponent("store.sqlite")
        )
        let context = ModelContext(reopened)
        let notes = try context.fetch(FetchDescriptor<ContentNote>())
        XCTAssertEqual(notes.count, 1)
        XCTAssertEqual(notes.first?.id, draft.id)
        XCTAssertEqual(notes.first?.transcriptText, draft.transcriptText)
        XCTAssertEqual(notes.first?.trashedAt, trashedAt)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 0)
    }

    func testPrepareForShareRoutesOnlyActiveNotes() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        XCTAssertEqual(try fixture.repository.prepareForShare(sourceKey: draft.sourceKey), .absent)
        _ = try fixture.repository.saveOrReuse(draft)
        try fixture.repository.acknowledge(routeIDs: fixture.repository.pendingRouteSnapshot().routeIDs)

        guard case let .activeRouted(active) = try fixture.repository.prepareForShare(sourceKey: draft.sourceKey) else {
            return XCTFail("Expected active route")
        }
        XCTAssertEqual(active.id, draft.id)
        XCTAssertEqual(try fixture.repository.pendingRouteSnapshot().noteID, draft.id)
        try fixture.repository.moveToTrash(noteID: draft.id, at: Date(timeIntervalSince1970: 2_000))

        guard case let .trashed(trashed) = try fixture.repository.prepareForShare(sourceKey: draft.sourceKey) else {
            return XCTFail("Expected trashed note")
        }
        XCTAssertEqual(trashed.id, draft.id)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
    }

    func testPurgeExpiredTrashIncludesCutoffAndCanRetry() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let cutoff = Date(timeIntervalSince1970: 30 * 24 * 60 * 60)
        let expired = makeDraft(id: UUID())
        let retained = makeDraft(id: UUID())
        let context = ModelContext(fixture.container)
        let expiredNote = ContentNote(draft: expired)
        expiredNote.sourceKey = expired.id.uuidString
        let retainedNote = ContentNote(draft: retained)
        retainedNote.sourceKey = retained.id.uuidString
        context.insert(expiredNote)
        context.insert(retainedNote)
        try context.save()
        try fixture.repository.moveToTrash(noteID: expired.id, at: cutoff)
        try fixture.repository.moveToTrash(noteID: retained.id, at: cutoff.addingTimeInterval(1))
        try fixture.repository.enqueueRoute(noteID: expired.id)

        let blockedRepository = ContentNoteRepository(
            container: fixture.container,
            lock: SharedStoreLock(fileURL: fixture.directory)
        )
        XCTAssertThrowsError(try blockedRepository.purgeExpiredTrash(cutoff: cutoff))
        XCTAssertNotNil(try fixture.repository.note(id: expired.id))

        XCTAssertEqual(try fixture.repository.purgeExpiredTrash(cutoff: cutoff), 1)
        XCTAssertNil(try fixture.repository.note(id: expired.id))
        XCTAssertNotNil(try fixture.repository.note(id: retained.id))
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
        XCTAssertEqual(try fixture.repository.purgeExpiredTrash(cutoff: cutoff), 0)
    }

    func testPrepareForShareCannotRouteANoteMovedToTrashConcurrently() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        _ = try fixture.repository.saveOrReuse(draft)
        try fixture.repository.acknowledge(routeIDs: fixture.repository.pendingRouteSnapshot().routeIDs)
        let secondRepository = ContentNoteRepository(
            container: try SharedModelContainer.make(at: fixture.directory.appendingPathComponent("store.sqlite")),
            lock: SharedStoreLock(fileURL: fixture.directory.appendingPathComponent("reforge-shared-store.lock"))
        )
        let sourceKey = draft.sourceKey
        let noteID = draft.id

        let prepareTask = Task.detached {
            try secondRepository.prepareForShare(sourceKey: sourceKey)
        }
        let trashTask = Task.detached {
            try fixture.repository.moveToTrash(noteID: noteID, at: Date(timeIntervalSince1970: 2_000))
        }
        _ = try await prepareTask.value
        try await trashTask.value

        XCTAssertNotNil(try fixture.repository.note(id: draft.id)?.trashedAt)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
    }

    func testConcurrentTrashAndSaveNeverCreateDuplicateOrRouteTrashedNote() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let draft = makeDraft()
        _ = try fixture.repository.saveOrReuse(draft)
        try fixture.repository.acknowledge(routeIDs: fixture.repository.pendingRouteSnapshot().routeIDs)
        let secondRepository = ContentNoteRepository(
            container: try SharedModelContainer.make(at: fixture.directory.appendingPathComponent("store.sqlite")),
            lock: SharedStoreLock(fileURL: fixture.directory.appendingPathComponent("reforge-shared-store.lock"))
        )
        let replacement = makeDraft(id: UUID(), title: "Concurrent replacement")
        let noteID = draft.id

        let saveTask = Task.detached { try secondRepository.saveOrReuse(replacement) }
        let trashTask = Task.detached {
            try fixture.repository.moveToTrash(noteID: noteID, at: Date(timeIntervalSince1970: 2_000))
        }
        _ = try await saveTask.value
        try await trashTask.value

        let context = ModelContext(fixture.container)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<ContentNote>()), 1)
        XCTAssertNotNil(try fixture.repository.note(id: draft.id)?.trashedAt)
        XCTAssertTrue(try fixture.repository.pendingRouteSnapshot().routeIDs.isEmpty)
    }

    private func makeFixture() throws -> (
        directory: URL,
        container: ModelContainer,
        repository: ContentNoteRepository
    ) {
        let directory = try makeDirectory()
        let container = try SharedModelContainer.make(
            at: directory.appendingPathComponent("store.sqlite")
        )
        let repository = ContentNoteRepository(
            container: container,
            lock: SharedStoreLock(
                fileURL: directory.appendingPathComponent("reforge-shared-store.lock")
            )
        )
        return (directory, container, repository)
    }

    private func makeDirectory() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        return directory
    }

    private func makeDraft(
        id: UUID = UUID(),
        sourceURL: URL = URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
        title: String = "First title",
        transcriptText: String = "First transcript",
        createdAt: Date = Date(timeIntervalSince1970: 1_000)
    ) -> ContentNoteDraft {
        ContentNoteDraft(
            id: id,
            sourceKey: "youtube:dQw4w9WgXcQ",
            sourceType: "youtube",
            videoId: "dQw4w9WgXcQ",
            sourceURL: sourceURL,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: title,
            transcriptId: "11111111-1111-4111-8111-111111111111",
            transcriptText: transcriptText,
            transcriptLanguageCode: "en",
            transcriptIsGenerated: false,
            createdAt: createdAt
        )
    }

    private func assertStored(
        _ stored: StoredContentNote,
        equals draft: ContentNoteDraft,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertEqual(stored.id, draft.id, file: file, line: line)
        XCTAssertEqual(stored.sourceURL, draft.sourceURL, file: file, line: line)
        XCTAssertEqual(stored.title, draft.title, file: file, line: line)
        XCTAssertEqual(stored.transcriptText, draft.transcriptText, file: file, line: line)
        XCTAssertEqual(stored.createdAt, draft.createdAt, file: file, line: line)
    }
}
