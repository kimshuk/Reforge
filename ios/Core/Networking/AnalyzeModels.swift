import Foundation

struct AnalyzeRequest: Codable {
    let type: String
    let title: String
    let youtubeUrl: String

    init(type: String = "youtube", title: String, youtubeUrl: String) {
        self.type = type
        self.title = title
        self.youtubeUrl = youtubeUrl
    }
}

struct AnalyzeResponse: Codable, Identifiable, Hashable {
    let transcriptId: String
    let sourceType: String
    let categories: [AnalyzeCategory]
    let expiresInSeconds: Int
    let videoId: String

    var id: String { transcriptId }
}

struct AnalyzeCategory: Codable, Hashable {
    let title: String
    let keywords: [AnalyzeKeyword]
}

struct AnalyzeKeyword: Codable, Hashable {
    let term: String
    let brief: String
    let level1: String
    let level2: String
    let level3: String
    let source: AnalyzeSource
}

struct AnalyzeSource: Codable, Hashable {
    let type: String
    let ref: String
}
