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

            ForEach(result.categories, id: \.title) { category in
                Section(category.title) {
                    ForEach(category.keywords, id: \.term) { keyword in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(keyword.term)
                                .font(.headline)

                            Text(keyword.brief)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)

                            Text("Level 1: \(keyword.level1)")
                            Text("Level 2: \(keyword.level2)")
                            Text("Level 3: \(keyword.level3)")

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
