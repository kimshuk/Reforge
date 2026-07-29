import Foundation
import XCTest
@testable import NoteApp

final class AnalyzeModelsTests: XCTestCase {
    func testDecodesDuplicateTermsAsDistinctServerOccurrences() throws {
        let result = try decode(
            """
            {
              "transcriptId": "transcript-1",
              "sourceType": "youtube",
              "categories": [{
                "categoryId": "category-openai",
                "title": "OpenAI",
                "keywords": [
                  {
                    "candidateClippingId": "occurrence-tool",
                    "term": "Codex",
                    "brief": "Autonomous coding tool introduced here",
                    "level1": "Codex performs coding tasks.",
                    "level2": "Codex is introduced as an autonomous tool.",
                    "level3": "The speaker introduces autonomous coding work.",
                    "source": {"type": "youtube", "ref": "https://example.com?t=46s"},
                    "sources": [{"type": "youtube", "ref": "https://example.com?t=46s"}]
                  },
                  {
                    "candidateClippingId": "occurrence-risk",
                    "term": "Codex",
                    "brief": "Competitive risk to software companies",
                    "level1": "Codex performs coding tasks.",
                    "level2": "Codex is discussed as a competitive risk.",
                    "level3": "The speaker connects autonomous coding to commercial pressure.",
                    "source": {"type": "youtube", "ref": "https://example.com?t=312s"},
                    "sources": [{"type": "youtube", "ref": "https://example.com?t=312s"}]
                  }
                ]
              }],
              "expiresInSeconds": 1800,
              "videoId": "video-1"
            }
            """
        )

        let category = try XCTUnwrap(result.categories.first)
        XCTAssertEqual(category.id, "category-openai")
        XCTAssertEqual(category.keywords.map(\.term), ["Codex", "Codex"])
        XCTAssertEqual(category.keywords.map(\.id), ["occurrence-tool", "occurrence-risk"])
        XCTAssertEqual(category.keywords.map(\.level2), [
            "Codex is introduced as an autonomous tool.",
            "Codex is discussed as a competitive risk.",
        ])
        XCTAssertEqual(category.keywords.map(\.level3), [
            "The speaker introduces autonomous coding work.",
            "The speaker connects autonomous coding to commercial pressure.",
        ])
        XCTAssertEqual(category.keywords.map(\.source.ref), [
            "https://example.com?t=46s",
            "https://example.com?t=312s",
        ])
        XCTAssertEqual(Set(category.keywords.map(\.id)).count, 2)
        XCTAssertEqual(category.keywords[0].sources.first, category.keywords[0].source)
        XCTAssertNotEqual(category.keywords[0].source, category.keywords[1].source)
    }

    func testLegacyPayloadUsesDeterministicPositionalFallbackIdentity() throws {
        let payload = """
        {
          "transcriptId": "legacy-transcript",
          "sourceType": "youtube",
          "categories": [{
            "title": "OpenAI",
            "keywords": [
              {"term": "Codex", "brief": "First context", "level1": "One", "level2": "Two", "level3": "Three", "source": {"type": "youtube", "ref": "https://example.com?t=46s"}},
              {"term": "Codex", "brief": "Second context", "level1": "One", "level2": "Different two", "level3": "Different three", "source": {"type": "youtube", "ref": "https://example.com?t=312s"}}
            ]
          }],
          "expiresInSeconds": 1800,
          "videoId": "video-1"
        }
        """

        let first = try decode(payload)
        let second = try decode(payload)
        let category = try XCTUnwrap(first.categories.first)

        XCTAssertEqual(category.id, "legacy-transcript:category:0")
        XCTAssertEqual(category.keywords.map(\.id), [
            "legacy-transcript:category:0:keyword:0",
            "legacy-transcript:category:0:keyword:1",
        ])
        XCTAssertEqual(first.categories.map(\.id), second.categories.map(\.id))
        XCTAssertEqual(category.keywords[0].sources, [category.keywords[0].source])
        XCTAssertNotEqual(category.keywords[0].id, category.keywords[1].id)
    }

    private func decode(_ json: String) throws -> AnalyzeResponse {
        try JSONDecoder().decode(AnalyzeResponse.self, from: Data(json.utf8))
    }
}

