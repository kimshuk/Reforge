import Combine
import Foundation
import SwiftUI

enum ShareExtensionPhase: Equatable {
    case idle
    case loading
    case awaitingRestore(UUID)
    case restoring(UUID)
    case finished
}

@MainActor
final class ShareExtensionViewModel: ObservableObject {
    @Published private(set) var phase: ShareExtensionPhase = .idle
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
        guard phase == .idle else { return }
        phase = .loading
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
            case .restoreRequired(let noteID):
                phase = .awaitingRestore(noteID)
                statusText = "This video is in Trash. Restore it?"
                isLoading = false
                return
            }
            isLoading = false
            await Task.yield()
            guard !Task.isCancelled else {
                finishWithCancel()
                return
            }
            guard phase == .loading else { return }
            phase = .finished
            complete()
        } catch let error as YouTubeTranscriptServiceError {
            isLoading = false
            guard !Task.isCancelled else {
                finishWithCancel()
                return
            }
            guard case let .backend(_, code, _) = error else {
                finishWithCancel()
                return
            }
            switch code {
            case "TRANSCRIPT_UNAVAILABLE", "EMPTY_TRANSCRIPT":
                statusText = "The video is available, but transcript is not available."
            case "TRANSCRIPT_PROVIDER_RATE_LIMITED", "TRANSCRIPT_PROVIDER_ERROR", "TRANSCRIPT_FETCH_FAILED":
                statusText = "Transcript provider failed. Please try again."
            default:
                finishWithCancel()
            }
            if phase == .loading { phase = .finished }
        } catch let error as URLError {
            isLoading = false
            guard !Task.isCancelled, error.code != .cancelled else {
                finishWithCancel()
                return
            }
            statusText = "Transcript provider failed. Please try again."
            phase = .finished
        } catch {
            finishWithCancel()
        }
    }

    func confirmRestore() async {
        guard case let .awaitingRestore(noteID) = phase else { return }
        phase = .restoring(noteID)
        isLoading = true
        do {
            let result = try await ingestor.restore(noteID: noteID)
            guard phase == .restoring(noteID) else { return }
            guard !Task.isCancelled, result == .alreadySaved(noteID: noteID) else {
                finishWithCancel()
                return
            }
            statusText = "Already saved"
            isLoading = false
            phase = .finished
            complete()
        } catch {
            guard phase == .restoring(noteID) else { return }
            finishWithCancel()
        }
    }

    func cancelRestore() {
        switch phase {
        case .awaitingRestore, .restoring:
            finishWithCancel()
        default:
            break
        }
    }

    private func finishWithCancel() {
        guard phase != .finished else { return }
        phase = .finished
        statusText = nil
        isLoading = false
        cancel()
    }
}
