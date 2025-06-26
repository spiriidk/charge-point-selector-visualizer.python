import csv
import os
from datetime import datetime, timedelta  # Import timedelta from datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html


# Initialize the Dash application
app = Dash(__name__)

# --- Robust consts.CSV_OUT_FOLDER Handling ---
# This block ensures that CSV_OUT_FOLDER is always defined,
# either from an existing consts.py or a default value.
consts_module = None
try:
    import consts as consts_module

    print("consts.py found and loaded.")
except ImportError:
    print("consts.py not found. Using default CSV_OUT_FOLDER='csv_reports'.")

# Determine the base folder for CSV reports
if consts_module and hasattr(consts_module, "CSV_OUT_FOLDER"):
    CSV_OUT_FOLDER = consts_module.CSV_OUT_FOLDER
else:
    CSV_OUT_FOLDER = "csv_reports"  # Default folder for reports

print(f"Using CSV_OUT_FOLDER: '{CSV_OUT_FOLDER}'")


def load_reports():
    """
    Loads report data from CSV files within subfolders of the defined CSV_OUT_FOLDER.
    Returns a nested dictionary: {folder_name: {file_name: [list_of_records]}}.
    Each record includes 'timestamp', 'total_error', and 'total_reduction'.
    """
    data = {}
    base_folder_path = Path(CSV_OUT_FOLDER)

    # Check if the base folder exists
    if not base_folder_path.exists() or not base_folder_path.is_dir():
        print(
            f"Base folder '{base_folder_path}' does not exist or is not a directory. Returning empty data."
        )
        return {}

    # Iterate through each item in the base folder
    for folder_name in os.listdir(base_folder_path):
        request_folder_path = base_folder_path / folder_name

        # Ensure it's a directory (i.e., a request folder)
        if not request_folder_path.is_dir():
            continue

        print(f"Loading data from folder: {folder_name}")
        data[folder_name] = {}  # Initialize a dictionary to hold files for this folder

        # Iterate through files within the request folder
        with os.scandir(request_folder_path) as it:
            for entry in it:
                # Process only CSV files
                if entry.is_file() and entry.name.endswith(".csv"):
                    file_path = request_folder_path / entry.name
                    print(f"  Processing file: {entry.name}")
                    records = []
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                try:
                                    # Parse timestamp and convert numeric values
                                    records.append({
                                        "timestamp": datetime.fromisoformat(
                                            row["timestamp"]
                                        ),
                                        "total_error": float(row["total_error"]),
                                        "total_reduction": float(
                                            row["total_reduction"]
                                        ),
                                    })
                                except (ValueError, KeyError) as e:
                                    print(
                                        f"    Skipping row in {file_path} due to parsing error: {e} - Row: {row}"
                                    )
                                    continue
                        # Store records for this file under the current folder
                        data[folder_name][entry.name] = records
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")
                        continue
    return data


# Load all available reports when the app starts
reports_data = load_reports()

# Prepare initial options for the folder dropdown
initial_folder_options = [
    {"label": folder, "value": folder} for folder in reports_data.keys()
]
initial_folder_value = list(reports_data.keys())[0] if reports_data else None

# Prepare initial options for the file dropdown based on the first selected folder
initial_file_options = []
initial_file_value = None
if initial_folder_value:
    files_in_initial_folder = reports_data[initial_folder_value]
    initial_file_options = [
        {"label": file, "value": file} for file in files_in_initial_folder.keys()
    ]
    initial_file_value = (
        list(files_in_initial_folder.keys())[0] if files_in_initial_folder else None
    )

# Define the application layout
app.layout = html.Div(
    [
        html.H1(
            "Error Reduction Over Time Dashboard",
            style={"textAlign": "center", "color": "#333"},
        ),
        html.Div(
            [
                html.Label(
                    "Select Request Folder:",
                    style={"fontWeight": "bold", "marginRight": "10px"},
                ),
                dcc.Dropdown(
                    id="folder-dropdown",
                    options=initial_folder_options,
                    value=initial_folder_value,
                    clearable=False,  # A folder should always be selected
                    style={
                        "width": "100%",
                        "maxWidth": "400px",
                        "marginBottom": "15px",
                    },
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "flexDirection": "column",
                "padding": "10px",
            },
        ),
        # Container for the file dropdown, conditionally displayed
        html.Div(
            [
                html.Label(
                    "Select File:", style={"fontWeight": "bold", "marginRight": "10px"}
                ),
                dcc.Dropdown(
                    id="file-dropdown",
                    options=initial_file_options,
                    value=initial_file_value,
                    clearable=False,  # A file should always be selected if the dropdown is visible
                    style={
                        "width": "100%",
                        "maxWidth": "400px",
                        "marginBottom": "20px",
                    },
                ),
            ],
            id="file-dropdown-container",
            # Use 'display: none' to hide completely and reclaim space
            style={
                "display": "flex" if initial_file_value else "none",
                "alignItems": "center",
                "justifyContent": "center",
                "flexDirection": "column",
                "padding": "10px",
                "marginTop": "10px",
            },
        ),
        dcc.Graph(
            id="error-plot", style={"height": "600px", "width": "90%", "margin": "auto"}
        ),
    ],
    style={
        "fontFamily": "Arial, sans-serif",
        "padding": "20px",
        "backgroundColor": "#f0f2f5",
    },
)


# Callback to update the file dropdown options based on the selected folder
@app.callback(
    Output("file-dropdown", "options"),
    Output("file-dropdown", "value"),
    Output("file-dropdown-container", "style"),  # Control display of file dropdown
    Input("folder-dropdown", "value"),
)
def update_file_dropdown(selected_folder):
    """
    Updates the options and selected value of the file dropdown based on the
    currently selected folder. Also controls the display of the file dropdown.
    """
    # Default style to hide the container
    display_style = {"display": "none"}
    file_options = []
    initial_file = None

    if selected_folder and selected_folder in reports_data:
        files_in_folder = reports_data.get(selected_folder, {})
        file_options = [
            {"label": file, "value": file} for file in files_in_folder.keys()
        ]

        # Set the default selected file to the first available file, if any
        if file_options:
            initial_file = file_options[0]["value"]
            # If files are available, show the container
            display_style = {
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "flexDirection": "column",
                "padding": "10px",
                "marginTop": "10px",
            }

    return file_options, initial_file, display_style


# Callback to update the plot based on both selected folder and file
@app.callback(
    Output("error-plot", "figure"),
    Input("folder-dropdown", "value"),
    Input("file-dropdown", "value"),
)
def update_plot(selected_folder, selected_file):
    """
    Generates and updates the Plotly graph based on the selected folder and file.
    """
    # Handle cases where no valid folder or file is selected (e.g., initial load or no data)
    if (
        not selected_folder
        or not selected_file
        or selected_folder not in reports_data
        or selected_file not in reports_data[selected_folder]
    ):
        # Return an empty figure with a descriptive title if no data can be plotted
        fig = px.line(
            title="Please select a folder and a file to view the error reduction data."
        )
        fig.update_layout(
            height=600,
            xaxis={"visible": False, "showticklabels": False},
            yaxis={"visible": False, "showticklabels": False},
            annotations=[
                {
                    "text": "No data available or selection incomplete.",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20},
                    "x": 0.5,
                    "y": 0.5,
                    "xanchor": "center",
                    "yanchor": "middle",
                }
            ],
            plot_bgcolor="#ffffff",
            paper_bgcolor="#f0f2f5",
        )
        return fig

    # Retrieve the specific records for the selected folder and file
    records = reports_data[selected_folder][selected_file]
    df = pd.DataFrame(records)

    # If the DataFrame is empty (e.g., file was empty or only had headers),
    # return an empty plot with a message
    # If the DataFrame is empty, return an informative plot
    if df.empty:
        fig = px.line(
            title=f"No data available for '{selected_file}' in '{selected_folder}'."
        )
        fig.update_layout(
            height=600,
            xaxis={"visible": False, "showticklabels": False},
            yaxis={"visible": False, "showticklabels": False},
            annotations=[
                {
                    "text": f"No plot data for {selected_file}",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20},
                    "x": 0.5,
                    "y": 0.5,
                    "xanchor": "center",
                    "yanchor": "middle",
                }
            ],
            plot_bgcolor="#ffffff",
            paper_bgcolor="#f0f2f5",
        )
        return fig

    # Ensure timestamp is parsed as datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Compute time elapsed in seconds
    df["time_elapsed_sec"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()

    # Create the line plot using elapsed time
    fig = px.line(
        df,
        x="time_elapsed_sec",
        y="total_error",
        title=f"Total Error Over Time – {selected_folder} / {selected_file}",
        labels={"total_error": "Total Error", "time_elapsed_sec": "Time Elapsed (s)"},
        line_shape="linear",
        render_mode="svg",
        markers=True,
    )

    # Update layout
    fig.update_layout(
        transition_duration=0,
        height=600,
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#f0f2f5",
        font_color="#333",
        title_font_size=24,
        xaxis_title_font_size=18,
        yaxis_title_font_size=18,
        hovermode="x unified",
    )

    # Customize axes
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#e0e0e0",
        title="Time Elapsed (seconds)",
    )
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#e0e0e0")

    return fig

if __name__ == "__main__":
    print("Starting Dash server...")
    app.run_server(debug=True)
