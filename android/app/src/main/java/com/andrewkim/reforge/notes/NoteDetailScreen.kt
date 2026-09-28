package com.andrewkim.reforge.notes

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.andrewkim.reforge.navigation.AnalysisInputSnapshot

@Composable
fun NoteDetailScreen(
    state: NoteDetailState,
    onMissing: () -> Unit,
    onOpenYoutube: (String) -> Unit,
    onAnalyze: (AnalysisInputSnapshot) -> Unit,
    onMoveToTrash: () -> Unit,
) {
    LaunchedEffect(state) { if (state == NoteDetailState.Missing) onMissing() }
    var showTrashConfirmation by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().testTag("note-detail").verticalScroll(rememberScrollState()).padding(16.dp)) {
        if (state is NoteDetailState.Ready) {
            val note = state.note
            Text("Note")
            Text(note.title, Modifier.testTag("detail-title"))
            AsyncImage(
                model = "https://img.youtube.com/vi/${note.videoId}/hqdefault.jpg",
                contentDescription = note.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth().aspectRatio(16f / 9f).testTag("note-thumbnail"),
            )
            TextButton(onClick = { onOpenYoutube(note.canonicalUrl) }) { Text("Open in YouTube") }
            note.transcriptLanguageCode?.let { Text("Language: $it") }
            note.transcriptIsGenerated?.let { Text(if (it) "Generated" else "Not generated") }
            Text(note.transcriptText, Modifier.testTag("note-transcript"))
            Button(onClick = {
                // Snapshot uses the note displayed by this composition, before navigation callbacks run.
                onAnalyze(AnalysisInputSnapshot(note.title, note.canonicalUrl))
            }) { Text("Analyze") }
            TextButton(onClick = { showTrashConfirmation = true }) { Text("Move to Trash") }
        }
    }
    if (showTrashConfirmation) AlertDialog(
        onDismissRequest = { showTrashConfirmation = false },
        text = { Text("Move this note to Trash? You can restore it for 30 days.") },
        confirmButton = { Button(onClick = {
            showTrashConfirmation = false
            onMoveToTrash()
        }, modifier = Modifier.testTag("confirm-move")) { Text("Move to Trash") } },
        dismissButton = { TextButton(onClick = { showTrashConfirmation = false }) { Text("Cancel") } },
    )
}
