package com.andrewkim.reforge.sharing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag

@Composable
fun ShareImportScreen(
    state: ShareImportState,
    onBack: () -> Unit,
    onCancelRestore: () -> Unit,
    onConfirmRestore: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().testTag("share-import"),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        when (state) {
            is ShareImportState.Loading, is ShareImportState.Completed ->
                CircularProgressIndicator(modifier = Modifier.testTag("share-loading"))
            is ShareImportState.Error -> {
                Text(state.message)
                Button(onClick = onBack) { Text("Back") }
            }
            is ShareImportState.AwaitingRestore -> AlertDialog(
                onDismissRequest = onCancelRestore,
                text = { Text("This video is in Trash. Restore it?") },
                confirmButton = { TextButton(onClick = onConfirmRestore) { Text("Restore") } },
                dismissButton = { TextButton(onClick = onCancelRestore) { Text("Cancel") } },
            )
            ShareImportState.Idle, is ShareImportState.Finished -> Unit
        }
    }
}
