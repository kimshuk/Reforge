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

struct AnalyzeResponse: Decodable, Identifiable, Hashable {
    let transcriptId: String
    let sourceType: String
    let categories: [AnalyzeCategory]
    let expiresInSeconds: Int
    let videoId: String?

    var id: String { transcriptId }

    private enum CodingKeys: String, CodingKey {
        case transcriptId
        case sourceType
        case categories
        case expiresInSeconds
        case videoId
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        transcriptId = try container.decode(String.self, forKey: .transcriptId)
        sourceType = try container.decode(String.self, forKey: .sourceType)
        expiresInSeconds = try container.decode(Int.self, forKey: .expiresInSeconds)
        videoId = try container.decodeIfPresent(String.self, forKey: .videoId)
        let payloads = try container.decode([AnalyzeCategoryPayload].self, forKey: .categories)
        categories = payloads.enumerated().map { categoryIndex, payload in
            let categoryIdentity = payload.categoryId ?? "\(transcriptId):category:\(categoryIndex)"
            return AnalyzeCategory(
                categoryId: payload.categoryId,
                id: categoryIdentity,
                title: payload.title,
                keywords: payload.keywords.enumerated().map { keywordIndex, keyword in
                    AnalyzeKeyword(
                        candidateClippingId: keyword.candidateClippingId,
                        id: keyword.candidateClippingId ?? "\(categoryIdentity):keyword:\(keywordIndex)",
                        term: keyword.term,
                        brief: keyword.brief,
                        level1: keyword.level1,
                        level2: keyword.level2,
                        level3: keyword.level3,
                        source: keyword.source,
                        sources: keyword.sources ?? [keyword.source],
                        level2CitationIds: keyword.level2CitationIds,
                        level3CitationIds: keyword.level3CitationIds,
                        externalSources: keyword.externalSources
                    )
                }
            )
        }
    }
}

struct AnalyzeCategory: Hashable, Identifiable {
    let categoryId: String?
    let id: String
    let title: String
    let keywords: [AnalyzeKeyword]
}

struct AnalyzeKeyword: Hashable, Identifiable {
    let candidateClippingId: String?
    let id: String
    let term: String
    let brief: String
    let level1: String
    let level2: String
    let level3: String
    let source: AnalyzeSource
    let sources: [AnalyzeSource]
    let level2CitationIds: [String]
    let level3CitationIds: [String]
    let externalSources: [AnalyzeExternalSource]

    func externalSources(forLevel level: Int) -> [AnalyzeExternalSource] {
        let ids = Set(level == 2 ? level2CitationIds : level == 3 ? level3CitationIds : [])
        return externalSources.filter { ids.contains($0.citationId) }
    }
}

struct AnalyzeExternalSource: Codable, Hashable, Identifiable {
    let citationId: String
    let title: String
    let url: String

    var id: String { citationId }
}

struct AnalyzeSource: Codable, Hashable {
    let type: String
    let ref: String
}

struct KeywordSelectionState: Equatable {
    private(set) var selectedKeywordIdsByCategory: [String: Set<String>] = [:]
    private(set) var displayLevelsByCategory: [String: [String: Int]] = [:]

    func isSelected(keywordId: String, in categoryId: String) -> Bool {
        selectedKeywordIdsByCategory[categoryId]?.contains(keywordId) ?? false
    }

    func level(keywordId: String, in categoryId: String) -> Int {
        displayLevelsByCategory[categoryId]?[keywordId] ?? 1
    }

    mutating func select(keywordId: String, in categoryId: String) {
        selectedKeywordIdsByCategory[categoryId, default: []].insert(keywordId)
        displayLevelsByCategory[categoryId, default: [:]][keywordId] = 1
    }

    mutating func advanceLevel(keywordId: String, in categoryId: String) {
        displayLevelsByCategory[categoryId, default: [:]][keywordId] =
            min(level(keywordId: keywordId, in: categoryId) + 1, 3)
    }

    mutating func remove(keywordId: String, from categoryId: String) {
        selectedKeywordIdsByCategory[categoryId]?.remove(keywordId)
        displayLevelsByCategory[categoryId]?.removeValue(forKey: keywordId)
    }

    mutating func reset() {
        self = KeywordSelectionState()
    }
}

private struct AnalyzeCategoryPayload: Decodable {
    let categoryId: String?
    let title: String
    let keywords: [AnalyzeKeywordPayload]
}

private struct AnalyzeKeywordPayload: Decodable {
    let candidateClippingId: String?
    let term: String
    let brief: String
    let level1: String
    let level2: String
    let level3: String
    let source: AnalyzeSource
    let sources: [AnalyzeSource]?
    let level2CitationIds: [String]
    let level3CitationIds: [String]
    let externalSources: [AnalyzeExternalSource]

    private enum CodingKeys: String, CodingKey {
        case candidateClippingId, term, brief, level1, level2, level3
        case source, sources, level2CitationIds, level3CitationIds, externalSources
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        candidateClippingId = try container.decodeIfPresent(String.self, forKey: .candidateClippingId)
        term = try container.decode(String.self, forKey: .term)
        brief = try container.decode(String.self, forKey: .brief)
        level1 = try container.decode(String.self, forKey: .level1)
        level2 = try container.decode(String.self, forKey: .level2)
        level3 = try container.decode(String.self, forKey: .level3)
        source = try container.decode(AnalyzeSource.self, forKey: .source)
        sources = try container.decodeIfPresent([AnalyzeSource].self, forKey: .sources)
        level2CitationIds = try container.decodeIfPresent([String].self, forKey: .level2CitationIds) ?? []
        level3CitationIds = try container.decodeIfPresent([String].self, forKey: .level3CitationIds) ?? []
        externalSources = try container.decodeIfPresent([AnalyzeExternalSource].self, forKey: .externalSources) ?? []
    }
}
