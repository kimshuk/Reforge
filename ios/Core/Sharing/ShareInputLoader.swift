import Foundation
import UniformTypeIdentifiers

enum ShareInputLoaderError: Error, Equatable {
    case invalidInput
    case loadFailed
    case unsupportedItem(String)
}

struct ShareInputLoader {
    func load(from extensionItems: [NSExtensionItem]) async throws -> SharedURLInput {
        try Task.checkCancellation()
        let attachments = extensionItems.flatMap { $0.attachments ?? [] }
        guard
            !attachments.isEmpty,
            attachments.allSatisfy({
                $0.hasItemConformingToTypeIdentifier(UTType.url.identifier)
            })
        else {
            throw ShareInputLoaderError.invalidInput
        }

        var urls: [URL] = []
        for provider in attachments {
            try Task.checkCancellation()
            urls.append(try await loadURL(from: provider))
        }
        try Task.checkCancellation()

        guard let url = urls.first else {
            throw ShareInputLoaderError.invalidInput
        }
        if urls.count > 1 {
            let videoIDs = try urls.map { url in
                do {
                    return try YouTubeVideoIdentity(url: url).videoID
                } catch {
                    throw ShareInputLoaderError.invalidInput
                }
            }
            guard Set(videoIDs).count == 1 else {
                throw ShareInputLoaderError.invalidInput
            }
        }

        let title = extensionItems
            .compactMap(\.attributedTitle?.string)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
        return SharedURLInput(url: url, sharedTitle: title)
    }

    private func loadURL(from provider: NSItemProvider) async throws -> URL {
        let item: NSSecureCoding = try await withCheckedThrowingContinuation { continuation in
            provider.loadItem(
                forTypeIdentifier: UTType.url.identifier,
                options: nil
            ) { item, error in
                if let error {
                    continuation.resume(throwing: error)
                } else if let item {
                    continuation.resume(returning: item)
                } else {
                    continuation.resume(throwing: ShareInputLoaderError.loadFailed)
                }
            }
        }

        let url: URL?
        if let value = item as? URL {
            url = value
        } else if let value = item as? NSURL {
            url = value as URL
        } else if let value = item as? String {
            url = URL(string: value)
        } else if let value = item as? Data {
            if let string = String(data: value, encoding: .utf8),
               let decodedURL = URL(string: string) {
                url = decodedURL
            } else if let decodedURL = try? NSKeyedUnarchiver.unarchivedObject(
                ofClass: NSURL.self,
                from: value
            ) {
                url = decodedURL as URL
            } else {
                url = nil
            }
        } else {
            url = nil
        }
        guard let url else {
            throw ShareInputLoaderError.unsupportedItem(
                String(reflecting: type(of: item))
            )
        }
        return url
    }
}
