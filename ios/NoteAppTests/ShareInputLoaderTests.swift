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
        let provider = NSItemProvider()
        provider.registerItem(forTypeIdentifier: UTType.url.identifier) { completion, _, _ in
            completion?(URL(string: "https://youtu.be/dQw4w9WgXcQ")! as NSURL, nil)
        }
        return provider
    }
}

private func assertThrows<T>(_ body: () async throws -> T) async {
    do {
        _ = try await body()
        XCTFail("Expected error")
    } catch {
    }
}
