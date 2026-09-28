import UIKit
import UniformTypeIdentifiers
import XCTest
@testable import NoteApp

@MainActor
final class ShareInputLoaderTests: XCTestCase {
    func testLoadsSingleURLAndAttributedTitle() async throws {
        let item = NSExtensionItem()
        item.attributedTitle = NSAttributedString(string: "  Shared title  ")
        item.attachments = [makeURLProvider()]

        let input = try await ShareInputLoader().load(from: [item])

        XCTAssertEqual(input.url.absoluteString, "https://youtu.be/dQw4w9WgXcQ")
        XCTAssertEqual(input.sharedTitle, "Shared title")
    }

    func testLoadsSafariAlternateURLsWhenTheyIdentifyTheSameVideo() async throws {
        let canonicalItem = NSExtensionItem()
        canonicalItem.attributedTitle = NSAttributedString(string: "Rick Astley")
        canonicalItem.attachments = [
            makeURLProvider("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ]
        let mobileItem = NSExtensionItem()
        mobileItem.attachments = [
            makeURLProvider("https://m.youtube.com/watch?v=dQw4w9WgXcQ&ra=m"),
        ]

        let input = try await ShareInputLoader().load(from: [canonicalItem, mobileItem])

        XCTAssertEqual(
            input.url.absoluteString,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        XCTAssertEqual(input.sharedTitle, "Rick Astley")
    }

    func testRejectsURLProvidersForDifferentVideos() async {
        let first = NSExtensionItem()
        first.attachments = [
            makeURLProvider("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ]
        let second = NSExtensionItem()
        second.attachments = [
            makeURLProvider("https://youtu.be/aqz-KE-bpKQ"),
        ]

        await assertThrows { try await ShareInputLoader().load(from: [first, second]) }
    }

    func testCancellationStopsBeforeLoadingTheNextURLProvider() async {
        let firstStarted = expectation(description: "first provider started")
        let secondStarted = expectation(description: "second provider must not start")
        secondStarted.isInverted = true
        let gate = ItemProviderCompletionGate()

        let first = NSExtensionItem()
        let firstProvider = NSItemProvider()
        firstProvider.registerItem(forTypeIdentifier: UTType.url.identifier) { completion, _, _ in
            gate.store(completion)
            firstStarted.fulfill()
        }
        first.attachments = [firstProvider]

        let second = NSExtensionItem()
        let secondProvider = NSItemProvider()
        secondProvider.registerItem(forTypeIdentifier: UTType.url.identifier) { completion, _, _ in
            secondStarted.fulfill()
            completion?(URL(string: "https://m.youtube.com/watch?v=dQw4w9WgXcQ")! as NSURL, nil)
        }
        second.attachments = [secondProvider]

        let task = Task {
            try await ShareInputLoader().load(from: [first, second])
        }
        await fulfillment(of: [firstStarted], timeout: 1)
        task.cancel()
        gate.complete(with: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!)

        await assertThrows { try await task.value }
        await fulfillment(of: [secondStarted], timeout: 0.1)
    }

    func testRejectsMissingURLAndAdditionalAttachment() async {
        await assertThrows { try await ShareInputLoader().load(from: [NSExtensionItem()]) }

        let item = NSExtensionItem()
        let textProvider = NSItemProvider()
        textProvider.registerDataRepresentation(forTypeIdentifier: UTType.plainText.identifier, visibility: .all) {
            $0(Data("extra".utf8), nil)
            return nil
        }
        item.attachments = [
            makeURLProvider(),
            textProvider,
        ]
        await assertThrows { try await ShareInputLoader().load(from: [item]) }
    }

    private func makeURLProvider() -> NSItemProvider {
        makeURLProvider("https://youtu.be/dQw4w9WgXcQ")
    }

    private func makeURLProvider(_ value: String) -> NSItemProvider {
        let provider = NSItemProvider()
        provider.registerItem(forTypeIdentifier: UTType.url.identifier) { completion, _, _ in
            completion?(URL(string: value)! as NSURL, nil)
        }
        return provider
    }
}

private final class ItemProviderCompletionGate: @unchecked Sendable {
    private let lock = NSLock()
    private var completion: NSItemProvider.CompletionHandler?

    func store(_ completion: NSItemProvider.CompletionHandler?) {
        lock.lock()
        self.completion = completion
        lock.unlock()
    }

    func complete(with url: URL) {
        lock.lock()
        let completion = self.completion
        self.completion = nil
        lock.unlock()
        completion?(url as NSURL, nil)
    }
}

private func assertThrows<T>(_ body: () async throws -> T) async {
    do {
        _ = try await body()
        XCTFail("Expected error")
    } catch {
    }
}
