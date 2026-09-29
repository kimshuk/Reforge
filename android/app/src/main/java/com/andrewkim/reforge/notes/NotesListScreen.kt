package com.andrewkim.reforge.notes

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

@Composable
fun NotesListScreen(
    notes: List<ContentNote>?,
    onOpenNote: (String) -> Unit,
    onOpenTrash: () -> Unit,
    onMoveToTrash: (String) -> Unit,
) {
    var pendingTrashId by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxSize().testTag("my-notes")) {
        Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("My Notes")
            TextButton(onClick = onOpenTrash) { Text("Trash") }
        }
        if (notes?.isEmpty() == true) Text("No saved notes yet.", Modifier.padding(16.dp))
        if (notes != null) LazyColumn {
            items(notes, key = ContentNote::id) { note ->
                Row(Modifier.fillMaxWidth().testTag("note-row-${note.id}").clickable { onOpenNote(note.id) }.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(note.title, Modifier.weight(1f))
                    TextButton(onClick = { pendingTrashId = note.id }) { Text("Move to Trash") }
                }
            }
        }
    }
    if (pendingTrashId != null) AlertDialog(
        onDismissRequest = { pendingTrashId = null },
        text = { Text("Move this note to Trash? You can restore it for 30 days.") },
        confirmButton = {
            Button(onClick = {
                pendingTrashId?.let(onMoveToTrash)
                pendingTrashId = null
            }, modifier = Modifier.testTag("confirm-move")) { Text("Move to Trash") }
        },
        dismissButton = { TextButton(onClick = { pendingTrashId = null }) { Text("Cancel") } },
    )
}
