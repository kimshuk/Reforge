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
        XCTAssertEqual(firstSnapshot.note?.id, draft.id)

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
        XCTAssertEqual(remaining.note?.id, draft.id)
    }

    func testSnapshotReturnsNilForLatestMissingNoteAndCanAcknowledgeIt() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        try fixture.repository.enqueueRoute(noteID: UUID())

        let snapshot = try fixture.repository.pendingRouteSnapshot()

        XCTAssertNil(snapshot.note)
        XCTAssertEqual(snapshot.routeIDs.count, 1)
        try fixture.repository.acknowledge(routeIDs: snapshot.routeIDs)
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
