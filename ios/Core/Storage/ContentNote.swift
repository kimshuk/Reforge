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
}

enum SaveNoteOutcome: Equatable, Sendable {
    case saved(StoredContentNote)
    case alreadySaved(StoredContentNote)
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
            createdAt: createdAt
        )
    }
}
