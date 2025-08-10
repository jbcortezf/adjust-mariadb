# MariaDB Advanced Database Synchronizer

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macOS-lightgrey.svg)

**Author:** João Cortez  
**Email:** jbcortezf@gmail.com  
**GitHub:** https://github.com/jbcortezf/adjust-mariadb

A powerful Python script that intelligently compares two MariaDB databases and provides granular control over schema and data synchronization. Perfect for database migrations, environment synchronization, and development workflows.

## 🚀 Features

- **Interactive Selection**: Choose table-by-table what to synchronize
- **Detailed Analysis**: See exactly what differs between databases
- **Flexible Sync Options**: Structure-only or structure+data for each table
- **Safe Operations**: Preview SQL before execution with rollback support
- **Comprehensive Logging**: Detailed progress and error reporting
- **Multi-Platform**: Works on Linux, Windows, and macOS
- **Smart Detection**: Identifies new columns, type changes, indexes, and constraints
- **Professional Output**: Generates clean, documented SQL files

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Examples](#examples)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🔧 Prerequisites

### System Requirements

- **Python 3.8+**
- **MariaDB/MySQL** server access
- **Network connectivity** to both database servers

### Database Permissions

The database users need the following permissions:

**Source Database (Read-only):**
```sql
GRANT SELECT, SHOW VIEW ON source_database.* TO 'user'@'%';
GRANT SHOW DATABASES ON *.* TO 'user'@'%';
```

**Target Database (Read-write):**
```sql
GRANT ALL PRIVILEGES ON target_database.* TO 'user'@'%';
GRANT CREATE, DROP ON *.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

## 📦 Installation

### Ubuntu/Debian

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and development tools
sudo apt install python3 python3-pip python3-venv python3-dev -y

# Install MariaDB development libraries
sudo apt install default-libmysqlclient-dev build-essential pkg-config -y

# Clone the repository
git clone https://github.com/jbcortezf/adjust-mariadb.git
cd adjust-mariadb

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install pymysql
```

### CentOS/RHEL/Fedora

```bash
# Install dependencies
sudo dnf install python3 python3-pip python3-devel mariadb-devel gcc -y

# Clone and setup
git clone https://github.com/jbcortezf/adjust-mariadb.git
cd adjust-mariadb
python3 -m venv venv
source venv/bin/activate
pip install pymysql
```

### Windows

```powershell
# Install Python from python.org (3.8+)
# Clone the repository
git clone https://github.com/jbcortezf/adjust-mariadb.git
cd adjust-mariadb

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install pymysql
```

### macOS

```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.9 mysql-client

# Clone and setup
git clone https://github.com/jbcortezf/adjust-mariadb.git
cd adjust-mariadb
python3 -m venv venv
source venv/bin/activate
pip install pymysql
```

## ⚙️ Configuration

Create a `databases.ini` file in the project directory:

```ini
[DEFAULT]
# SOURCE Database Configuration (Database 1)
database1ip = localhost
database1user = marketplace
database1password = your_password_here
database1name = production_db

# TARGET Database Configuration (Database 2)
database2ip = localhost
database2user = marketplace
database2password = your_password_here
database2name = staging_db
```

### Configuration Examples

**Local Development:**
```ini
database1ip = localhost
database1name = production_db
database2name = development_db
```

**Remote Server Sync:**
```ini
database1ip = prod-server.company.com
database1user = sync_user
database1name = production
database2ip = staging-server.company.com
database2user = staging_user
database2name = staging
```

**Cross-Environment Migration:**
```ini
database1ip = 192.168.1.100
database1name = legacy_system
database2ip = cloud-db.amazonaws.com
database2name = new_system
```

### Security Best Practices

```bash
# Protect configuration file
chmod 600 databases.ini

# Use environment variables (optional)
export DB1_PASSWORD="your_secure_password"
export DB2_PASSWORD="your_secure_password"
```

## 🎯 Usage

### Basic Usage

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows

# Run the script
python3 adjustdb.py
```

### Command Flow

1. **Connection**: Script connects to both databases
2. **Analysis**: Analyzes and compares database structures
3. **Review**: Shows detailed differences summary
4. **Selection**: Interactive table-by-table selection
5. **Generation**: Creates SQL synchronization scripts
6. **Execution**: Optional immediate application of changes

## 📚 Examples

### Example 1: Development Environment Sync

**Scenario**: Sync production structure to development environment

```bash
$ python3 adjustdb.py
================================================================================
MARIADB ADVANCED DATABASE SYNCHRONIZER
Author: João Cortez | Email: jbcortezf@gmail.com
GitHub: https://github.com/jbcortezf/adjust-mariadb
================================================================================
✓ Successfully connected to both databases
  - Source: production at prod-server.com
  - Target: development at localhost

🔍 Analyzing differences between 'production' and 'development'...
📊 Analyzing database: production
   Found 45 tables
📊 Analyzing database: development
   Found 40 tables

🔍 Detailed comparison:
   Source database (production): 45 tables
   Target database (development): 40 tables
   Common tables: 40
   → New: 5
   → Removed: 0
   → Modified: 8
   → Identical: 32

📋 NEW TABLES (5 tables):
   • user_preferences (1,247 records)
   • audit_logs (45,892 records)
   • feature_flags (23 records)
   • payment_methods (156 records)
   • notifications (8,934 records)

🔧 MODIFIED TABLES (8 tables):
   • users (source: 15,432 → target: 15,401 records)
     → New columns: mobile_phone, last_login_ip
     → Modified columns: email
```

**Interactive Selection:**
```
============================================================
📋 TABLE DETAILS: users
============================================================
📊 RECORDS: Source 15,432 → Target 15,401

➕ NEW COLUMNS (2):
   • mobile_phone: varchar(20) NULL
   • last_login_ip: varchar(45) NULL

🔧 MODIFIED COLUMNS (1):
   • email:
     - Type: varchar(100) → varchar(150)

🤔 What to do with table 'users'?
   Choose (1/2/s/d): 1
    ✅ users: Structure only
```

### Example 2: Full Migration with Data

**Scenario**: Complete database migration including data

```ini
# databases.ini
database1ip = old-server.company.com
database1name = legacy_crm
database2ip = new-server.company.com
database2name = modern_crm
```

**Selection Strategy:**
- **Structure Only**: Large tables with existing data
- **Structure + Data**: Configuration tables, lookup tables
- **Skip**: Deprecated or test tables

### Example 3: Staging Environment Refresh

**Monthly staging refresh workflow:**

```bash
# 1. Backup current staging
mysqldump -h staging-server.com staging_db > staging_backup.sql

# 2. Run synchronization
python3 adjustdb.py

# 3. Select structure-only for user data tables
# 4. Select structure+data for configuration tables
```

## 🔬 Advanced Features

### Detailed Structural Analysis

The script provides comprehensive analysis including:

- **Column Changes**: Type, nullability, defaults, extra attributes
- **Index Differences**: New, removed, or modified indexes
- **Foreign Key Constraints**: Relationship changes
- **Table Engine**: Storage engine differences
- **Character Set**: Charset and collation changes

### Smart SQL Generation

Generated SQL includes:

```sql
-- Structure Synchronization Script
-- Generated by: MariaDB Advanced Database Synchronizer
-- Author: João Cortez (jbcortezf@gmail.com)
-- GitHub: https://github.com/jbcortezf/adjust-mariadb
-- Generated on: 2025-01-15 14:30:25
-- Source: production → Target: staging

USE `staging`;
SET FOREIGN_KEY_CHECKS = 0;

-- Creating table user_preferences
CREATE TABLE `user_preferences` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `preference_key` varchar(100) NOT NULL,
  `preference_value` text,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Modifying table structure users
ALTER TABLE `users` ADD COLUMN `mobile_phone` varchar(20) NULL;
ALTER TABLE `users` MODIFY COLUMN `email` varchar(150) NOT NULL;

SET FOREIGN_KEY_CHECKS = 1;
```

### Batch Operations

For large datasets, the script provides guidance:

```sql
-- WARNING: Data for table audit_logs must be exported separately
-- due to large volume (1,245,892 records)
-- Use: mysqldump -h prod-server.com -u sync_user -p production audit_logs --no-create-info
```

### Error Handling and Recovery

- **Transaction Support**: Automatic rollback on errors
- **Progress Tracking**: Real-time execution feedback
- **Detailed Logging**: Comprehensive error messages
- **Safe Defaults**: Conservative operation choices

## 🔍 Output Files

The script generates several files:

- **`sync_database_structure.sql`**: DDL commands for structure changes
- **`sync_database_data.sql`**: Data synchronization guidance
- **`adjustdb.log`**: Detailed execution log (if logging enabled)

## 🛠️ Troubleshooting

### Common Issues

**Connection Refused:**
```bash
# Check MariaDB service
sudo systemctl status mariadb

# Verify network connectivity
telnet database-server.com 3306

# Check user permissions
mysql -h server -u username -p -e "SHOW GRANTS;"
```

**Permission Denied:**
```sql
-- Grant necessary permissions
GRANT SELECT, SHOW VIEW ON source_db.* TO 'user'@'%';
GRANT ALL PRIVILEGES ON target_db.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

**Module Not Found:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install --upgrade pymysql
```

**Character Encoding Issues:**
```bash
# Set proper locale
export LC_ALL=en_US.UTF-8

# Verify database charset
mysql -e "SHOW VARIABLES LIKE 'character_set%';"
```

### Debug Mode

For detailed debugging, modify the script to enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Tips

- **Large Databases**: Use structure-only for tables with millions of records
- **Network Latency**: Consider running script closer to database servers
- **Resource Usage**: Monitor memory usage for very large schemas

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/adjust-mariadb.git

# Create development environment
cd adjust-mariadb
python3 -m venv dev-env
source dev-env/bin/activate
pip install pymysql pytest black flake8

# Run tests
python -m pytest tests/

# Format code
black adjustdb.py

# Lint code
flake8 adjustdb.py
```

### Contribution Guidelines

- **Code Style**: Follow PEP 8 using `black` formatter
- **Testing**: Add tests for new features
- **Documentation**: Update README.md for new features
- **Commit Messages**: Use clear, descriptive commit messages

## 📊 Roadmap

- [ ] **GUI Interface**: Web-based interface for easier management
- [ ] **Schema Versioning**: Track and manage schema versions
- [ ] **Automated Scheduling**: Cron/scheduler integration
- [ ] **Multiple Database Support**: PostgreSQL, SQLite support
- [ ] **Cloud Integration**: AWS RDS, Google Cloud SQL support
- [ ] **Performance Metrics**: Execution time and resource usage tracking
- [ ] **Configuration Management**: Multiple environment profiles

## 📄 License

This project is licensed under the MIT License - see the details below:

```
MIT License

Copyright (c) 2025 João Cortez

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🆘 Support

If you encounter any issues or have questions:

1. **Check** the [Troubleshooting](#troubleshooting) section
2. **Search** existing [GitHub Issues](https://github.com/jbcortezf/adjust-mariadb/issues)
3. **Create** a new issue with detailed information
4. **Contact** via email: jbcortezf@gmail.com

## 🙏 Acknowledgments

- **MariaDB Foundation** for the excellent database system
- **PyMySQL** team for the reliable Python connector
- **Python Community** for the robust ecosystem
- **Contributors** who help improve this tool

---

**⭐ If this tool helps you, please consider giving it a star on GitHub!**

Made with ❤️ by [João Cortez](https://github.com/jbcortezf)
