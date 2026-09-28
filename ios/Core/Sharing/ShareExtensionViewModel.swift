import Combine
import Foundation
import SwiftUI

@MainActor
final class ShareExtensionViewModel: ObservableObject {
    @Published private(set) var statusText: String?
    @Published private(set) var isLoading = false

    private let ingestor: any ShareIngesting
    private let complete: () -> Void
    private let cancel: () -> Void

    init(
        ingestor: any ShareIngesting,
        complete: @escaping () -> Void,
        cancel: @escaping () -> Void
    ) {
        self.ingestor = ingestor
        self.complete = complete
        self.cancel = cancel
    }

    func run(input: SharedURLInput) async {
        isLoading = true
        statusText = nil
        do {
            let result = try await ingestor.ingest(input)
            try Task.checkCancellation()
            switch result {
            case .saved:
                statusText = "Saved to Reforge"
            case .alreadySaved:
                statusText = "Already saved"
            }
            isLoading = false
            await Task.yield()
            guard !Task.isCancelled else {
                cancel()
                return
            }
            complete()
        } catch let error as YouTubeTranscriptServiceError {
            isLoading = false
            guard !Task.isCancelled else {
                cancel()
                return
            }
            guard case let .backend(_, code, _) = error else {
                cancel()
                return
            }
            switch code {
            case "TRANSCRIPT_UNAVAILABLE", "EMPTY_TRANSCRIPT":
                statusText = "The video is available, but transcript is not available."
            case "TRANSCRIPT_PROVIDER_RATE_LIMITED", "TRANSCRIPT_PROVIDER_ERROR", "TRANSCRIPT_FETCH_FAILED":
                statusText = "Transcript provider failed. Please try again."
            default:
                cancel()
            }
        } catch let error as URLError {
            isLoading = false
            guard !Task.isCancelled, error.code != .cancelled else {
                cancel()
                return
            }
            statusText = "Transcript provider failed. Please try again."
        } catch {
            isLoading = false
            cancel()
        }
    }
}
