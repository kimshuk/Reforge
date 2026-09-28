package com.andrewkim.reforge.notes

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
fun TrashScreen(
    notes: List<ContentNote>?,
    onRestore: (String) -> Unit,
    onDelete: (String) -> Unit,
) {
    var pendingDeleteId by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxSize().testTag("trash")) {
        Text("Trash", Modifier.padding(16.dp))
        if (notes?.isEmpty() == true) Text("Trash is empty.", Modifier.padding(16.dp))
        if (notes != null) LazyColumn {
            items(notes, key = ContentNote::id) { note ->
                Row(Modifier.fillMaxWidth().testTag("trash-row-${note.id}").padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(note.title, Modifier.weight(1f))
                    TextButton(onClick = { onRestore(note.id) }) { Text("Restore") }
                    TextButton(onClick = { pendingDeleteId = note.id }) { Text("Delete") }
                }
            }
        }
    }
    if (pendingDeleteId != null) AlertDialog(
        onDismissRequest = { pendingDeleteId = null },
        text = { Text("Delete this note permanently? This can’t be undone.") },
        confirmButton = { Button(onClick = {
            pendingDeleteId?.let(onDelete)
            pendingDeleteId = null
        }, modifier = Modifier.testTag("confirm-delete")) { Text("Delete") } },
        dismissButton = { TextButton(onClick = { pendingDeleteId = null }) { Text("Cancel") } },
    )
}
