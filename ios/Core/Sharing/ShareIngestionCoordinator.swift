import Foundation

enum ShareIngestionResult: Equatable, Sendable {
    case saved(noteID: UUID)
    case alreadySaved(noteID: UUID)
}

enum ShareIngestionError: Error, Equatable {
    case videoIdentityMismatch
}

protocol ShareIngesting {
    func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult
}

protocol ContentNotePersisting {
    func find(sourceKey: String) throws -> StoredContentNote?
    func saveOrReuse(_ draft: ContentNoteDraft) throws -> SaveNoteOutcome
    func enqueueRoute(noteID: UUID) throws
}

extension ContentNoteRepository: ContentNotePersisting {}

final class ShareIngestionCoordinator {
    private let repository: any ContentNotePersisting
    private let transcriptService: any YouTubeTranscriptFetching
    private let titleResolver: any ShareTitleResolving
    private let now: () -> Date

    init(
        repository: any ContentNotePersisting,
        transcriptService: any YouTubeTranscriptFetching,
        titleResolver: any ShareTitleResolving = ShareTitleResolver(),
        now: @escaping () -> Date = Date.init
    ) {
        self.repository = repository
        self.transcriptService = transcriptService
        self.titleResolver = titleResolver
        self.now = now
    }

    func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult {
        let identity = try YouTubeVideoIdentity(url: input.url)
        if let existing = try repository.find(sourceKey: identity.sourceKey) {
            try repository.enqueueRoute(noteID: existing.id)
            return .alreadySaved(noteID: existing.id)
        }

        let sharedTitle = normalizedTitle(input.sharedTitle)
        let transcript: YouTubeTranscriptResponse
        let resolvedTitle: String?
        if let sharedTitle {
            transcript = try await transcriptService.fetch(
                youtubeURL: identity.canonicalURL,
                title: sharedTitle
            )
            resolvedTitle = sharedTitle
        } else {
            async let transcriptTask = transcriptService.fetch(
                youtubeURL: identity.canonicalURL,
                title: nil
            )
            async let titleTask = titleResolver.resolveTitle(
                for: identity.canonicalURL
            )
            (transcript, resolvedTitle) = try await (transcriptTask, titleTask)
        }

        guard transcript.videoId == identity.videoID else {
            throw ShareIngestionError.videoIdentityMismatch
        }
        try Task.checkCancellation()

        let draft = ContentNoteDraft(
            id: UUID(),
            sourceKey: identity.sourceKey,
            sourceType: "youtube",
            videoId: identity.videoID,
            sourceURL: input.url,
            canonicalURL: identity.canonicalURL,
            title: resolvedTitle ?? identity.canonicalURL.absoluteString,
            transcriptId: transcript.transcriptId,
            transcriptText: transcript.transcriptText,
            transcriptLanguageCode: transcript.languageCode,
            transcriptIsGenerated: transcript.isGenerated,
            createdAt: now()
        )

        switch try repository.saveOrReuse(draft) {
        case .saved(let note):
            return .saved(noteID: note.id)
        case .alreadySaved(let note):
            return .alreadySaved(noteID: note.id)
        }
    }

    private func normalizedTitle(_ title: String?) -> String? {
        guard let title else { return nil }
        let value = title.trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }
}

extension ShareIngestionCoordinator: ShareIngesting {}
