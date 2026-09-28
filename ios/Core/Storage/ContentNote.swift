import Foundation
import SwiftData

struct ContentNoteDraft: Equatable, Sendable {
    let id: UUID
    let sourceKey: String
    let sourceType: String
    let videoId: String
    let sourceURL: URL
    let canonicalURL: URL
    let title: String
    let transcriptId: String
    let transcriptText: String
    let transcriptLanguageCode: String?
    let transcriptIsGenerated: Bool?
    let createdAt: Date
}

struct StoredContentNote: Equatable, Sendable {
    let id: UUID
    let sourceKey: String
    let sourceType: String
    let videoId: String
    let sourceURL: URL
    let canonicalURL: URL
    let title: String
    let transcriptId: String
    let transcriptText: String
    let transcriptLanguageCode: String?
    let transcriptIsGenerated: Bool?
    let createdAt: Date
    let trashedAt: Date?

    init(
        id: UUID,
        sourceKey: String,
        sourceType: String,
        videoId: String,
        sourceURL: URL,
        canonicalURL: URL,
        title: String,
        transcriptId: String,
        transcriptText: String,
        transcriptLanguageCode: String?,
        transcriptIsGenerated: Bool?,
        createdAt: Date,
        trashedAt: Date? = nil
    ) {
        self.id = id
        self.sourceKey = sourceKey
        self.sourceType = sourceType
        self.videoId = videoId
        self.sourceURL = sourceURL
        self.canonicalURL = canonicalURL
        self.title = title
        self.transcriptId = transcriptId
        self.transcriptText = transcriptText
        self.transcriptLanguageCode = transcriptLanguageCode
        self.transcriptIsGenerated = transcriptIsGenerated
        self.createdAt = createdAt
        self.trashedAt = trashedAt
    }
}

enum ShareNotePreparation: Equatable, Sendable {
    case activeRouted(StoredContentNote)
    case trashed(StoredContentNote)
    case absent
}

enum SaveNoteOutcome: Equatable, Sendable {
    case saved(StoredContentNote)
    case alreadySaved(StoredContentNote)
    case restoreRequired(StoredContentNote)
}

@Model
final class ContentNote {
    var id: UUID
    var sourceKey: String
    var sourceType: String
    var videoId: String
    var sourceURL: URL
    var canonicalURL: URL
    var title: String
    var transcriptId: String
    var transcriptText: String
    var transcriptLanguageCode: String?
    var transcriptIsGenerated: Bool?
    var createdAt: Date
    var trashedAt: Date?

    init(draft: ContentNoteDraft) {
        id = draft.id
        sourceKey = draft.sourceKey
        sourceType = draft.sourceType
        videoId = draft.videoId
        sourceURL = draft.sourceURL
        canonicalURL = draft.canonicalURL
        title = draft.title
        transcriptId = draft.transcriptId
        transcriptText = draft.transcriptText
        transcriptLanguageCode = draft.transcriptLanguageCode
        transcriptIsGenerated = draft.transcriptIsGenerated
        createdAt = draft.createdAt
        trashedAt = nil
    }

    var stored: StoredContentNote {
        StoredContentNote(
            id: id,
            sourceKey: sourceKey,
            sourceType: sourceType,
            videoId: videoId,
            sourceURL: sourceURL,
            canonicalURL: canonicalURL,
            title: title,
            transcriptId: transcriptId,
            transcriptText: transcriptText,
            transcriptLanguageCode: transcriptLanguageCode,
            transcriptIsGenerated: transcriptIsGenerated,
            createdAt: createdAt,
            trashedAt: trashedAt
        )
    }
}
