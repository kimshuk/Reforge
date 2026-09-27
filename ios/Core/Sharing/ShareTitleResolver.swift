import Foundation

protocol ShareTitleResolving {
    func resolveTitle(for canonicalURL: URL) async -> String?
}

struct ShareTitleResolver: ShareTitleResolving {
    private let service: any YouTubeTitleService
    private let timeoutNanoseconds: UInt64

    init(
        service: any YouTubeTitleService = YouTubeOEmbedService(),
        timeoutNanoseconds: UInt64 = 1_500_000_000
    ) {
        self.service = service
        self.timeoutNanoseconds = timeoutNanoseconds
    }

    func resolveTitle(for canonicalURL: URL) async -> String? {
        await withTaskGroup(of: String?.self) { group in
            group.addTask {
                do {
                    let result = try await service.checkAvailability(
                        for: canonicalURL.absoluteString
                    )
                    guard case let .available(title) = result else { return nil }
                    let value = title.trimmingCharacters(in: .whitespacesAndNewlines)
                    return value.isEmpty ? nil : value
                } catch {
                    return nil
                }
            }
            group.addTask {
                try? await Task.sleep(nanoseconds: timeoutNanoseconds)
                return nil
            }
            let result = await group.next() ?? nil
            group.cancelAll()
            return result
        }
    }
}
