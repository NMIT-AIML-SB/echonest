package com.example.echonest;

import android.app.DatePickerDialog;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.util.Calendar;

public class RecTargetActivity extends AppCompatActivity {

    private Spinner spinnerLocation;
    private Spinner spinnerDay;
    private Spinner spinnerTime;

    private Button buttonDate;
    private Button buttonCommit;

    private TextView textTarget;

    private String selectedDate = "Not selected";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_rec_target);

        // Connect XML views
        spinnerLocation = findViewById(R.id.spinnerLocation);
        spinnerDay = findViewById(R.id.spinnerDay);
        spinnerTime = findViewById(R.id.spinnerTime);

        buttonDate = findViewById(R.id.buttonDate);
        buttonCommit = findViewById(R.id.buttonCommit);

        textTarget = findViewById(R.id.textTarget);


        // =====================================================
        // LOCATION
        // =====================================================

        String[] locations = {
                "All Locations",
                "Bengaluru",
                "Cubbon Park",
                "Lalbagh",
                "Yelahanka"
        };

        spinnerLocation.setAdapter(
                createSpinnerAdapter(locations)
        );


        // =====================================================
        // DAY
        // =====================================================

        String[] days = {
                "Any Day",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday"
        };

        spinnerDay.setAdapter(
                createSpinnerAdapter(days)
        );


        // =====================================================
        // TIME
        // =====================================================

        String[] times = {
                "Any Time",
                "6:00 AM - 7:00 AM",
                "7:00 AM - 8:00 AM",
                "8:00 AM - 9:00 AM",
                "5:00 PM - 6:00 PM",
                "6:00 PM - 7:00 PM"
        };

        spinnerTime.setAdapter(
                createSpinnerAdapter(times)
        );


        // =====================================================
        // LOCATION CHANGE
        // =====================================================

        spinnerLocation.setOnItemSelectedListener(
                new AdapterView.OnItemSelectedListener() {

                    @Override
                    public void onItemSelected(
                            AdapterView<?> parent,
                            View view,
                            int position,
                            long id) {

                        applyFilters();
                    }

                    @Override
                    public void onNothingSelected(
                            AdapterView<?> parent) {
                    }
                }
        );


        // =====================================================
        // DAY CHANGE
        // =====================================================

        spinnerDay.setOnItemSelectedListener(
                new AdapterView.OnItemSelectedListener() {

                    @Override
                    public void onItemSelected(
                            AdapterView<?> parent,
                            View view,
                            int position,
                            long id) {

                        applyFilters();
                    }

                    @Override
                    public void onNothingSelected(
                            AdapterView<?> parent) {
                    }
                }
        );


        // =====================================================
        // TIME CHANGE
        // =====================================================

        spinnerTime.setOnItemSelectedListener(
                new AdapterView.OnItemSelectedListener() {

                    @Override
                    public void onItemSelected(
                            AdapterView<?> parent,
                            View view,
                            int position,
                            long id) {

                        applyFilters();
                    }

                    @Override
                    public void onNothingSelected(
                            AdapterView<?> parent) {
                    }
                }
        );


        // =====================================================
        // DATE
        // =====================================================

        buttonDate.setOnClickListener(v -> {

            Calendar calendar = Calendar.getInstance();

            int year = calendar.get(Calendar.YEAR);
            int month = calendar.get(Calendar.MONTH);
            int day = calendar.get(Calendar.DAY_OF_MONTH);

            DatePickerDialog datePickerDialog =
                    new DatePickerDialog(
                            RecTargetActivity.this,

                            (view, selectedYear,
                             selectedMonth, selectedDay) -> {

                                selectedDate =
                                        selectedDay + "/" +
                                                (selectedMonth + 1) + "/" +
                                                selectedYear;

                                buttonDate.setText(selectedDate);

                                applyFilters();
                            },

                            year,
                            month,
                            day
                    );

            datePickerDialog.show();
        });


        // =====================================================
        // TARGET CLICK
        // =====================================================

        textTarget.setOnClickListener(v -> {

            Toast.makeText(
                    RecTargetActivity.this,
                    "Target selected",
                    Toast.LENGTH_SHORT
            ).show();

            textTarget.setBackgroundResource(
                    R.drawable.target_selected
            );
        });


        // =====================================================
        // COMMIT
        // =====================================================

        buttonCommit.setOnClickListener(v -> {

            Toast.makeText(
                    RecTargetActivity.this,
                    "Target committed successfully",
                    Toast.LENGTH_LONG
            ).show();
        });


        // Show initial target
        applyFilters();
    }


    // =========================================================
    // CREATE WHITE TEXT SPINNER
    // =========================================================

    private ArrayAdapter<String> createSpinnerAdapter(
            String[] items) {

        return new ArrayAdapter<String>(
                this,
                android.R.layout.simple_spinner_item,
                items
        ) {

            @Override
            public View getView(
                    int position,
                    View convertView,
                    ViewGroup parent) {

                TextView textView = (TextView)
                        super.getView(
                                position,
                                convertView,
                                parent
                        );

                textView.setTextColor(Color.WHITE);
                textView.setTextSize(14);
                textView.setPadding(
                        8,
                        0,
                        8,
                        0
                );

                return textView;
            }

            @Override
            public View getDropDownView(
                    int position,
                    View convertView,
                    ViewGroup parent) {

                TextView textView = (TextView)
                        super.getDropDownView(
                                position,
                                convertView,
                                parent
                        );

                textView.setTextColor(Color.BLACK);
                textView.setTextSize(14);
                textView.setPadding(
                        16,
                        16,
                        16,
                        16
                );

                return textView;
            }
        };
    }


    // =========================================================
    // APPLY FILTERS
    // =========================================================

    private void applyFilters() {

        String location =
                spinnerLocation.getSelectedItem().toString();

        String day =
                spinnerDay.getSelectedItem().toString();

        String time =
                spinnerTime.getSelectedItem().toString();


        String targetNumber;
        String targetLocation;
        String targetDay;
        String targetTime;
        String coordinates;


        // =====================================================
        // SAMPLE TARGETS
        // =====================================================

        if (location.equals("Cubbon Park")) {

            targetNumber = "Target 02";
            targetLocation = "Cubbon Park";
            targetDay = "Monday";
            targetTime = "7:00 AM - 8:00 AM";
            coordinates = "12.9763, 77.5929";

        } else if (location.equals("Lalbagh")) {

            targetNumber = "Target 03";
            targetLocation = "Lalbagh";
            targetDay = "Wednesday";
            targetTime = "7:00 AM - 8:00 AM";
            coordinates = "12.9507, 77.5848";

        } else if (location.equals("Yelahanka")) {

            targetNumber = "Target 04";
            targetLocation = "Yelahanka";
            targetDay = "Friday";
            targetTime = "6:00 AM - 7:00 AM";
            coordinates = "13.1007, 77.5963";

        } else {

            targetNumber = "Target 01";
            targetLocation = "Bengaluru";
            targetDay = "Monday";
            targetTime = "6:00 AM - 7:00 AM";
            coordinates = "12.9716, 77.5946";
        }


        // =====================================================
        // DAY FILTER
        // =====================================================

        if (!day.equals("Any Day")
                && !day.equals(targetDay)) {

            showNoTarget();
            return;
        }


        // =====================================================
        // TIME FILTER
        // =====================================================

        if (!time.equals("Any Time")
                && !time.equals(targetTime)) {

            showNoTarget();
            return;
        }


        // =====================================================
        // SHOW TARGET
        // =====================================================

        String targetText =
                targetNumber + "\n" +
                        targetLocation + "\n" +
                        coordinates + "\n" +
                        targetDay + "\n" +
                        targetTime;

        if (!selectedDate.equals("Not selected")) {

            targetText +=
                    "\nDate: " + selectedDate;
        }

        textTarget.setText(targetText);

        textTarget.setVisibility(View.VISIBLE);
    }


    // =========================================================
    // NO TARGET
    // =========================================================

    private void showNoTarget() {

        textTarget.setText(
                "No targets available\n\n" +
                        "Try changing the location, day or time."
        );

        textTarget.setVisibility(View.VISIBLE);
    }
}