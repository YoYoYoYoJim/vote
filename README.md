# Random Number UI App

This project is a simple application that generates random numbers using a user-friendly interface. It is built with Python and includes a graphical user interface (GUI) for easy interaction.

## Project Structure

```
random-number-ui-app
├── src
│   ├── app.py               # Entry point of the application
│   ├── ui
│   │   └── main_window.py   # Defines the main window of the UI
│   ├── services
│   │   └── random_generator.py # Contains the random number generation logic
│   └── types
│       └── __init__.py      # Custom types or interfaces (if needed)
├── requirements.txt         # Project dependencies
└── README.md                # Project documentation
```

## Installation

To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd random-number-ui-app
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command:

```
python src/app.py
```

This will launch the user interface where you can generate random numbers.

## CPU Topology Audit Script

This repository also includes a Linux audit framework for CPU topology validation:

```
python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out
```

Useful options:

```
python3 scripts/cpu_topology_audit.py \
   --output-dir cpu_topology_audit_out \
   --baseline cpu_topology_audit_out/snapshot.json \
   --expected-threads-per-core 2 \
   --expected-numa-nodes 2 \
   --required-acpi-tables MADT,SRAT,PPTT \
   --irq 120 --irq 121
```

Outputs:

```
cpu_topology_audit_out/report.txt
cpu_topology_audit_out/summary.json
cpu_topology_audit_out/snapshot.json
```

The script is intended for Linux targets and emits PASS, FAIL, or SKIP for the 10 topology checks discussed earlier.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.