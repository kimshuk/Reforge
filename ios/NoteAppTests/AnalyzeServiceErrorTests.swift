import XCTest
@testable import NoteApp

final class AnalyzeServiceErrorTests: XCTestCase {
    private let analysisFailed = "Analysis failed on the backend. Please try again."
    private let serverMessage = "Provider detail https://provider.example?api_key=secret"

    func testCurrentBackendCodesUseFriendlyMessages() {
        for (code, expected) in [
            ("INVALID_YOUTUBE_URL", "Invalid YouTube URL. Please check and try again."),
            ("TRANSCRIPT_UNAVAILABLE", "The video is available, but transcript is not available."),
            ("TRANSCRIPT_FETCH_FAILED", "Transcript provider failed. Please try again."),
            ("INVALID_TRANSCRIPT", "Backend returned an invalid transcript response."),
            ("EMPTY_TRANSCRIPT", "This video has an empty transcript."),
            ("SHORT_TRANSCRIPT", "This video is too short to analyze."),
            ("LLM_QUOTA_OR_RATE_LIMIT", "The analysis service is busy. Please try again shortly."),
            ("LLM_CONTEXT_LENGTH_EXCEEDED", "This video is too long to analyze."),
            ("LLM_AUTH_ERROR", "The analysis service isn't available right now."),
            ("LLM_PROVIDER_NOT_CONFIGURED", "The analysis service isn't available right now."),
        ] {
            XCTAssertEqual(description(code: code), expected, code)
        }
    }

    func testAnalysisFailureCodesHideServerMessage() {
        for code in [
            "INVALID_CATEGORY_GRAPH",
            "LLM_CATEGORY_GROUPING_INVALID_JSON",
            "LLM_CLIPPINGS_INVALID_JSON",
            "LLM_CLIPPINGS_INVALID_SOURCE_REF",
            "LLM_EMPTY_OUTPUT",
            "LLM_ENRICHMENT_PLAN_INVALID_JSON",
            "LLM_ENRICHMENT_REVIEW_INVALID_JSON",
            "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON",
            "LLM_REQUEST_FAILED",
            "LLM_RESPONSE_INCOMPLETE",
            "LLM_TOPIC_CHUNKS_EMPTY",
            "LLM_TOPIC_CHUNKS_INVALID_BOUNDARY",
            "LLM_TOPIC_CHUNKS_INVALID_JSON",
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
        ] {
            XCTAssertEqual(description(code: code), analysisFailed, code)
        }
    }

    func testRemovedBackendCodesFallBackToServerMessage() {
        for code in [
            "OPENAI_QUOTA_OR_RATE_LIMIT",
            "OPENAI_AUTH_ERROR",
            "OPENAI_API_KEY_MISSING",
            "PYTHON_RUNTIME_ERROR",
            "YOUTUBE_VIDEO_UNAVAILABLE",
            "TRANSCRIPT_PROVIDER_ERROR",
        ] {
            XCTAssertEqual(description(code: code), serverMessage, code)
        }
    }

    func testUnknownCodeFallsBackToServerMessage() {
        XCTAssertEqual(description(code: "SOMETHING_NEW"), serverMessage)
    }

    func testUnknownCodeWithoutServerMessageNamesTheCode() {
        XCTAssertEqual(
            description(code: "SOMETHING_NEW", message: ""),
            "Request failed with code SOMETHING_NEW."
        )
    }

    private func description(code: String, message: String? = nil) -> String? {
        AnalyzeServiceError.backendError(
            code: code,
            message: message ?? serverMessage,
            videoId: nil
        ).errorDescription
    }
}
