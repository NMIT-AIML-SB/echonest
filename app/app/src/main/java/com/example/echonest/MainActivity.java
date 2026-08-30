package com.example.echonest;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);


        // =====================================================
        // FR03 - FIND REC TARGET
        // =====================================================

        findViewById(R.id.cardFindTarget).setOnClickListener(v -> {

            Intent intent = new Intent(
                    MainActivity.this,
                    RecTargetActivity.class
            );

            startActivity(intent);
        });


        // =====================================================
        // FR05 - REC AT TARGET
        // =====================================================

        findViewById(R.id.cardRecTarget).setOnClickListener(v -> {

            Toast.makeText(
                    MainActivity.this,
                    "Rec at Target will be available soon",
                    Toast.LENGTH_SHORT
            ).show();

        });


        // =====================================================
        // FR07 - REC EXPLORATORY
        // =====================================================

        findViewById(R.id.cardExploratory).setOnClickListener(v -> {

            Toast.makeText(
                    MainActivity.this,
                    "Exploratory Recording will be available soon",
                    Toast.LENGTH_SHORT
            ).show();

        });


        // =====================================================
        // FR08 - RECORDING LIST
        // =====================================================

        findViewById(R.id.cardRecordingList).setOnClickListener(v -> {

            Toast.makeText(
                    MainActivity.this,
                    "Recording List will be available soon",
                    Toast.LENGTH_SHORT
            ).show();

        });


        // =====================================================
        // BIRD OF THE DAY - LISTEN
        // =====================================================

        findViewById(R.id.buttonListen).setOnClickListener(v -> {

            Toast.makeText(
                    MainActivity.this,
                    "Bird sound playback will be available soon",
                    Toast.LENGTH_SHORT
            ).show();

        });


        // =====================================================
        // BIRD OF THE DAY - LEARN MORE
        // =====================================================

        findViewById(R.id.buttonLearnMore).setOnClickListener(v -> {

            Toast.makeText(
                    MainActivity.this,
                    "More bird information will be available soon",
                    Toast.LENGTH_SHORT
            ).show();

        });


        // =====================================================
        // MENU
        // =====================================================

        findViewById(R.id.textMenu).setOnClickListener(v -> {

            Toast.makeText(
                    MainActivity.this,
                    "Profile / Logout menu coming soon",
                    Toast.LENGTH_SHORT
            ).show();

        });

    }
}