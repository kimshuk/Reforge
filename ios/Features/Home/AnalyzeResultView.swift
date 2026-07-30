import SwiftUI

struct AnalyzeResultView: View {
    let result: AnalyzeResponse

    var body: some View {
        List {
            Section("Summary") {
                KeyValueRow(title: "Transcript ID", value: result.transcriptId)
                KeyValueRow(title: "Video ID", value: result.videoId ?? "N/A")
                KeyValueRow(title: "Source Type", value: result.sourceType)
            }

            ForEach(result.categories) { category in
                Section(category.title) {
                    ForEach(category.keywords) { keyword in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(keyword.term)
                                .font(.headline)

                            Text(keyword.brief)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)

                            Text("Level 1: \(keyword.level1)")
                            Text("Level 2: \(keyword.level2)")
                            externalLinks(keyword.externalSources(forLevel: 2))
                            Text("Level 3: \(keyword.level3)")
                            externalLinks(keyword.externalSources(forLevel: 3))

                            if let url = URL(string: keyword.source.ref) {
                                Link("Source: \(keyword.source.ref)", destination: url)
                                    .font(.footnote)
                                    .foregroundStyle(.blue)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
        }
        .navigationTitle("Analysis Result")
        .navigationBarTitleDisplayMode(.inline)
    }

    @ViewBuilder
    private func externalLinks(_ sources: [AnalyzeExternalSource]) -> some View {
        ForEach(sources) { source in
            if let url = URL(string: source.url) {
                Link(source.title, destination: url)
                    .font(.footnote)
            }
        }
    }
}

private struct KeyValueRow: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.body)
        }
    }
}
