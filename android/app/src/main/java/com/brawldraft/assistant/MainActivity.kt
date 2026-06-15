package com.brawldraft.assistant

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import com.brawldraft.assistant.ui.draft.ManualDraftScreen
import com.brawldraft.assistant.ui.theme.AppBackgroundGradient
import com.brawldraft.assistant.ui.theme.BrawlDraftAssistantTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            BrawlDraftAssistantTheme {
                // Scaffold transparente sobre el degradado de fondo de la app.
                Scaffold(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(AppBackgroundGradient),
                    containerColor = Color.Transparent,
                ) { innerPadding ->
                    ManualDraftScreen(modifier = Modifier.padding(innerPadding))
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun MainPreview() {
    BrawlDraftAssistantTheme {
        ManualDraftScreen()
    }
}
