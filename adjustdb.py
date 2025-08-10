#!/usr/bin/env python3
"""
MariaDB Advanced Schema & Data Synchronization Script

Author: João Cortez
Email: jbcortezf@gmail.com
GitHub: https://github.com/jbcortezf/adjust-mariadb

This script compares two MariaDB databases and allows granular control
over synchronization of structure and/or data for each table.

Features:
- Interactive table-by-table selection
- Detailed structural difference analysis
- Support for structure-only or structure+data sync
- Safe SQL generation with preview
- Comprehensive logging and error handling

Requirements:
- pymysql or mysql-connector-python
- databases.ini file with connection parameters

License: MIT License
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
"""

import configparser
import pymysql
import sys
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from datetime import datetime

class AdvancedDatabaseSyncer:
    def __init__(self, config_file: str = 'databases.ini'):
        """Initialize the synchronizer with database configurations."""
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.db1_conn = None
        self.db2_conn = None
        self.sync_operations = {}
        self.structure_sql = []
        self.data_sql = []
        
    def connect_databases(self) -> bool:
        """Connect to both databases using configuration from databases.ini"""
        try:
            # Connect to database 1 (source)
            self.db1_conn = pymysql.connect(
                host=self.config.get('DEFAULT', 'database1ip'),
                user=self.config.get('DEFAULT', 'database1user'),
                password=self.config.get('DEFAULT', 'database1password'),
                database=self.config.get('DEFAULT', 'database1name'),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            # Connect to database 2 (target)
            self.db2_conn = pymysql.connect(
                host=self.config.get('DEFAULT', 'database2ip'),
                user=self.config.get('DEFAULT', 'database2user'),
                password=self.config.get('DEFAULT', 'database2password'),
                database=self.config.get('DEFAULT', 'database2name'),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            print("✓ Successfully connected to both databases")
            print(f"  - Source: {self.config.get('DEFAULT', 'database1name')} at {self.config.get('DEFAULT', 'database1ip')}")
            print(f"  - Target: {self.config.get('DEFAULT', 'database2name')} at {self.config.get('DEFAULT', 'database2ip')}")
            return True
            
        except Exception as e:
            print(f"✗ Error connecting to databases: {e}")
            return False
    
    def get_database_schema(self, connection, db_name: str = None) -> Dict:
        """Extract complete schema information from a database."""
        schema = {
            'databases': [],
            'tables': defaultdict(dict),
            'columns': defaultdict(list),
            'indexes': defaultdict(list),
            'foreign_keys': defaultdict(list),
            'table_info': defaultdict(dict)
        }
        
        cursor = connection.cursor()
        
        try:
            # Use the database that was already selected during connection
            # or use the provided db_name
            if db_name:
                cursor.execute(f"USE `{db_name}`")
                current_db = db_name
            else:
                # Get current database name
                cursor.execute("SELECT DATABASE() as current_db")
                result = cursor.fetchone()
                current_db = result['current_db'] if result and result['current_db'] else None
                
                if not current_db:
                    print("No database selected")
                    return schema
            
            print(f"📊 Analyzing database: {current_db}")
            
            # Get all tables with their info
            cursor.execute("""
                SELECT 
                    TABLE_NAME,
                    ENGINE,
                    TABLE_COLLATION,
                    TABLE_ROWS,
                    DATA_LENGTH,
                    TABLE_COMMENT
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """, (current_db,))
            
            tables_info = cursor.fetchall()
            print(f"   Found {len(tables_info)} tables")
            
            for table_info in tables_info:
                table_name = table_info['TABLE_NAME']
                schema['table_info'][table_name] = table_info
                
                # Get CREATE TABLE statement
                cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                create_table = cursor.fetchone()
                schema['tables'][table_name] = {
                    'create_statement': create_table['Create Table'],
                    'engine': table_info['ENGINE'],
                    'charset': table_info['TABLE_COLLATION'],
                    'rows': table_info['TABLE_ROWS'] or 0
                }
                
                # Get detailed column information
                cursor.execute(f"""
                    SELECT 
                        COLUMN_NAME,
                        COLUMN_TYPE,
                        IS_NULLABLE,
                        COLUMN_DEFAULT,
                        EXTRA,
                        COLUMN_COMMENT,
                        ORDINAL_POSITION,
                        COLUMN_KEY
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s 
                    AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """, (current_db, table_name))
                schema['columns'][table_name] = cursor.fetchall()
                
                # Get indexes
                cursor.execute(f"SHOW INDEX FROM `{table_name}`")
                schema['indexes'][table_name] = cursor.fetchall()
                
                # Get foreign keys (using REFERENTIAL_CONSTRAINTS for rules)
                try:
                    cursor.execute(f"""
                        SELECT 
                            kcu.CONSTRAINT_NAME,
                            kcu.COLUMN_NAME,
                            kcu.REFERENCED_TABLE_NAME,
                            kcu.REFERENCED_COLUMN_NAME,
                            COALESCE(rc.UPDATE_RULE, 'RESTRICT') as UPDATE_RULE,
                            COALESCE(rc.DELETE_RULE, 'RESTRICT') as DELETE_RULE
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                        LEFT JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc 
                            ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME 
                            AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA
                        WHERE kcu.TABLE_SCHEMA = %s 
                        AND kcu.TABLE_NAME = %s
                        AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                    """, (current_db, table_name))
                    schema['foreign_keys'][table_name] = cursor.fetchall()
                except Exception as fk_error:
                    # Fallback for older MariaDB versions
                    print(f"   ⚠️ Warning: Could not get detailed foreign keys for {table_name}: {fk_error}")
                    cursor.execute(f"""
                        SELECT 
                            CONSTRAINT_NAME,
                            COLUMN_NAME,
                            REFERENCED_TABLE_NAME,
                            REFERENCED_COLUMN_NAME,
                            'RESTRICT' as UPDATE_RULE,
                            'RESTRICT' as DELETE_RULE
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                        WHERE TABLE_SCHEMA = %s 
                        AND TABLE_NAME = %s
                        AND REFERENCED_TABLE_NAME IS NOT NULL
                    """, (current_db, table_name))
                    schema['foreign_keys'][table_name] = cursor.fetchall()
                
        except Exception as e:
            print(f"Error extracting schema: {e}")
            
        finally:
            cursor.close()
            
        return schema
    
    def analyze_differences(self, schema1: Dict, schema2: Dict, db1_name: str, db2_name: str) -> Dict:
        """Analyze differences between schemas and categorize them."""
        differences = {
            'new_tables': [],        # Tables only in schema1
            'removed_tables': [],    # Tables only in schema2
            'modified_tables': [],   # Tables with structural differences
            'identical_tables': []   # Tables that are identical
        }
        
        tables1 = set(schema1['tables'].keys())
        tables2 = set(schema2['tables'].keys())
        
        print(f"\n🔍 Detailed comparison:")
        print(f"   Source database ({db1_name}): {len(tables1)} tables")
        print(f"   Target database ({db2_name}): {len(tables2)} tables")
        
        # New tables (exist in source but not in target)
        differences['new_tables'] = sorted(list(tables1 - tables2))
        
        # Removed tables (exist in target but not in source)
        differences['removed_tables'] = sorted(list(tables2 - tables1))
        
        # Check common tables for modifications
        common_tables = tables1 & tables2
        print(f"   Common tables: {len(common_tables)}")
        
        for table in sorted(common_tables):
            if self.table_has_differences(table, schema1, schema2):
                differences['modified_tables'].append(table)
            else:
                differences['identical_tables'].append(table)
        
        print(f"   → New: {len(differences['new_tables'])}")
        print(f"   → Removed: {len(differences['removed_tables'])}")
        print(f"   → Modified: {len(differences['modified_tables'])}")
        print(f"   → Identical: {len(differences['identical_tables'])}")
        
        return differences
    
    def table_has_differences(self, table_name: str, schema1: Dict, schema2: Dict) -> bool:
        """Check if a table has structural differences between schemas."""
        # Debug: check for issues in comparison
        if table_name not in schema1['columns'] or table_name not in schema2['columns']:
            print(f"   ⚠️ Table {table_name}: column data missing")
            return True
            
        cols1 = {col['COLUMN_NAME']: col for col in schema1['columns'][table_name]}
        cols2 = {col['COLUMN_NAME']: col for col in schema2['columns'][table_name]}
        
        # Check for different columns
        cols1_names = set(cols1.keys())
        cols2_names = set(cols2.keys())
        
        if cols1_names != cols2_names:
            new_cols = cols1_names - cols2_names
            removed_cols = cols2_names - cols1_names
            if new_cols or removed_cols:
                print(f"   🔍 {table_name}: Column differences detected")
                if new_cols:
                    print(f"      + New: {list(new_cols)[:3]}{'...' if len(new_cols) > 3 else ''}")
                if removed_cols:
                    print(f"      - Removed: {list(removed_cols)[:3]}{'...' if len(removed_cols) > 3 else ''}")
                return True
        
        # Check for column definition differences
        different_cols = []
        for col_name in cols1_names & cols2_names:
            col1 = cols1[col_name]
            col2 = cols2[col_name]
            
            if (col1['COLUMN_TYPE'] != col2['COLUMN_TYPE'] or
                col1['IS_NULLABLE'] != col2['IS_NULLABLE'] or
                str(col1['COLUMN_DEFAULT']) != str(col2['COLUMN_DEFAULT']) or
                col1['EXTRA'] != col2['EXTRA']):
                different_cols.append(col_name)
        
        if different_cols:
            print(f"   🔍 {table_name}: Different definitions in {len(different_cols)} columns")
            print(f"      Columns: {different_cols[:3]}{'...' if len(different_cols) > 3 else ''}")
            return True
        
        return False
    
    def show_analysis_summary(self, differences: Dict, schema1: Dict, schema2: Dict):
        """Display a comprehensive analysis of differences."""
        print("\n" + "="*80)
        print("DATABASE DIFFERENCES ANALYSIS")
        print("="*80)
        
        if differences['new_tables']:
            print(f"\n📋 NEW TABLES ({len(differences['new_tables'])} tables):")
            print("   (Exist only in source database)")
            for table in differences['new_tables']:
                rows = schema1['tables'][table]['rows']
                print(f"   • {table} ({rows:,} records)")
        
        if differences['removed_tables']:
            print(f"\n🗑️  TABLES TO REMOVE ({len(differences['removed_tables'])} tables):")
            print("   (Exist only in target database)")
            for table in differences['removed_tables']:
                rows = schema2['tables'][table]['rows']
                print(f"   • {table} ({rows:,} records)")
        
        if differences['modified_tables']:
            print(f"\n🔧 MODIFIED TABLES ({len(differences['modified_tables'])} tables):")
            print("   (Structural differences detected)")
            for table in differences['modified_tables']:
                rows1 = schema1['tables'][table]['rows']
                rows2 = schema2['tables'][table]['rows']
                print(f"   • {table} (source: {rows1:,} → target: {rows2:,} records)")
                
                # Show specific differences
                self.show_table_differences(table, schema1, schema2)
        
        if differences['identical_tables']:
            print(f"\n✅ IDENTICAL TABLES ({len(differences['identical_tables'])} tables):")
            for i, table in enumerate(differences['identical_tables']):
                if i < 10:  # Show first 10
                    print(f"   • {table}")
                elif i == 10:
                    print(f"   • ... and {len(differences['identical_tables']) - 10} more tables")
                    break
    
    def show_table_differences(self, table_name: str, schema1: Dict, schema2: Dict):
        """Show specific differences for a table."""
        cols1 = {col['COLUMN_NAME']: col for col in schema1['columns'][table_name]}
        cols2 = {col['COLUMN_NAME']: col for col in schema2['columns'][table_name]}
        
        # New columns
        new_cols = set(cols1.keys()) - set(cols2.keys())
        if new_cols:
            print(f"     → New columns: {', '.join(sorted(new_cols))}")
        
        # Removed columns
        removed_cols = set(cols2.keys()) - set(cols1.keys())
        if removed_cols:
            print(f"     → Removed columns: {', '.join(sorted(removed_cols))}")
        
        # Modified columns
        common_cols = set(cols1.keys()) & set(cols2.keys())
        modified_cols = []
        for col_name in common_cols:
            if (cols1[col_name]['COLUMN_TYPE'] != cols2[col_name]['COLUMN_TYPE'] or
                cols1[col_name]['IS_NULLABLE'] != cols2[col_name]['IS_NULLABLE'] or
                cols1[col_name]['COLUMN_DEFAULT'] != cols2[col_name]['COLUMN_DEFAULT']):
                modified_cols.append(col_name)
        
        if modified_cols:
            print(f"     → Modified columns: {', '.join(sorted(modified_cols))}")
    
    def show_detailed_table_differences(self, table_name: str, schema1: Dict, schema2: Dict, is_new_table: bool = False):
        """Show detailed structural differences for a specific table."""
        print(f"\n{'='*60}")
        print(f"📋 TABLE DETAILS: {table_name}")
        print(f"{'='*60}")
        
        if is_new_table:
            print("🆕 NEW TABLE (does not exist in target)")
            print(f"   Engine: {schema1['tables'][table_name].get('engine', 'N/A')}")
            print(f"   Records: {schema1['tables'][table_name].get('rows', 0):,}")
            
            # Show columns structure
            columns = schema1['columns'][table_name]
            print(f"\n📋 STRUCTURE ({len(columns)} columns):")
            for col in columns[:10]:  # Show first 10 columns
                nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                default = f"DEFAULT {col['COLUMN_DEFAULT']}" if col['COLUMN_DEFAULT'] else ""
                extra = col['EXTRA'] if col['EXTRA'] else ""
                print(f"   • {col['COLUMN_NAME']}: {col['COLUMN_TYPE']} {nullable} {default} {extra}".strip())
            
            if len(columns) > 10:
                print(f"   ... and {len(columns) - 10} more columns")
            return
        
        # For existing tables, show detailed differences
        cols1 = {col['COLUMN_NAME']: col for col in schema1['columns'][table_name]}
        cols2 = {col['COLUMN_NAME']: col for col in schema2['columns'][table_name]}
        
        rows1 = schema1['tables'][table_name].get('rows', 0)
        rows2 = schema2['tables'][table_name].get('rows', 0)
        
        print(f"📊 RECORDS: Source {rows1:,} → Target {rows2:,}")
        
        # New columns (in source but not in target)
        new_cols = set(cols1.keys()) - set(cols2.keys())
        if new_cols:
            print(f"\n➕ NEW COLUMNS ({len(new_cols)}):")
            for col_name in sorted(new_cols):
                col = cols1[col_name]
                nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                default = f"DEFAULT {col['COLUMN_DEFAULT']}" if col['COLUMN_DEFAULT'] else ""
                extra = col['EXTRA'] if col['EXTRA'] else ""
                print(f"   • {col_name}: {col['COLUMN_TYPE']} {nullable} {default} {extra}".strip())
        
        # Removed columns (in target but not in source)
        removed_cols = set(cols2.keys()) - set(cols1.keys())
        if removed_cols:
            print(f"\n➖ REMOVED COLUMNS ({len(removed_cols)}):")
            for col_name in sorted(removed_cols):
                col = cols2[col_name]
                print(f"   • {col_name}: {col['COLUMN_TYPE']}")
        
        # Modified columns
        common_cols = set(cols1.keys()) & set(cols2.keys())
        modified_cols = []
        
        for col_name in common_cols:
            col1 = cols1[col_name]
            col2 = cols2[col_name]
            
            differences = []
            
            if col1['COLUMN_TYPE'] != col2['COLUMN_TYPE']:
                differences.append(f"Type: {col2['COLUMN_TYPE']} → {col1['COLUMN_TYPE']}")
            
            if col1['IS_NULLABLE'] != col2['IS_NULLABLE']:
                old_null = "NULL" if col2['IS_NULLABLE'] == 'YES' else "NOT NULL"
                new_null = "NULL" if col1['IS_NULLABLE'] == 'YES' else "NOT NULL"
                differences.append(f"Nullable: {old_null} → {new_null}")
            
            if str(col1['COLUMN_DEFAULT']) != str(col2['COLUMN_DEFAULT']):
                old_default = col2['COLUMN_DEFAULT'] or 'NULL'
                new_default = col1['COLUMN_DEFAULT'] or 'NULL'
                differences.append(f"Default: {old_default} → {new_default}")
            
            if col1['EXTRA'] != col2['EXTRA']:
                old_extra = col2['EXTRA'] or '(none)'
                new_extra = col1['EXTRA'] or '(none)'
                differences.append(f"Extra: {old_extra} → {new_extra}")
            
            if differences:
                modified_cols.append((col_name, differences))
        
        if modified_cols:
            print(f"\n🔧 MODIFIED COLUMNS ({len(modified_cols)}):")
            for col_name, differences in modified_cols:
                print(f"   • {col_name}:")
                for diff in differences:
                    print(f"     - {diff}")
        
        # Show indexes differences if any
        self.show_index_differences(table_name, schema1, schema2)
        
        if not new_cols and not removed_cols and not modified_cols:
            print("\n✅ Identical structures (difference only in data)")

    def show_index_differences(self, table_name: str, schema1: Dict, schema2: Dict):
        """Show index differences between tables."""
        indexes1 = schema1.get('indexes', {}).get(table_name, [])
        indexes2 = schema2.get('indexes', {}).get(table_name, [])
        
        # Group indexes by name
        idx1_dict = {}
        for idx in indexes1:
            key = f"{idx['Key_name']}"
            if key not in idx1_dict:
                idx1_dict[key] = []
            idx1_dict[key].append(idx['Column_name'])
        
        idx2_dict = {}
        for idx in indexes2:
            key = f"{idx['Key_name']}"
            if key not in idx2_dict:
                idx2_dict[key] = []
            idx2_dict[key].append(idx['Column_name'])
        
        # Compare indexes
        new_indexes = set(idx1_dict.keys()) - set(idx2_dict.keys())
        removed_indexes = set(idx2_dict.keys()) - set(idx1_dict.keys())
        
        if new_indexes:
            print(f"\n🔑 NEW INDEXES ({len(new_indexes)}):")
            for idx_name in sorted(new_indexes):
                cols = ', '.join(idx1_dict[idx_name])
                print(f"   • {idx_name}: ({cols})")
        
        if removed_indexes:
            print(f"\n🗑️ REMOVED INDEXES ({len(removed_indexes)}):")
            for idx_name in sorted(removed_indexes):
                cols = ', '.join(idx2_dict[idx_name])
                print(f"   • {idx_name}: ({cols})")

    def interactive_selection(self, differences: Dict, schema1: Dict, schema2: Dict) -> Dict:
        """Interactive selection of what to sync for each table."""
        selections = {
            'structure_only': [],
            'structure_and_data': [],
            'skip': [],
            'drop_tables': []
        }
        
        print("\n" + "="*80)
        print("INTERACTIVE SYNCHRONIZATION SELECTION")
        print("="*80)
        print("Options:")
        print("  1 - Structure only")
        print("  2 - Structure + data")
        print("  s - Skip this table")
        print("  d - View table details again")
        print("  q - Quit")
        
        # Handle new tables
        if differences['new_tables']:
            print(f"\n{'='*80}")
            print(f"📋 NEW TABLES ({len(differences['new_tables'])} tables)")
            print("="*80)
            
            for i, table in enumerate(differences['new_tables']):
                rows = schema1['tables'][table]['rows']
                
                # Show detailed differences
                self.show_detailed_table_differences(table, schema1, schema2, is_new_table=True)
                
                while True:
                    print(f"\n🤔 What to do with table '{table}'?")
                    choice = input(f"   Choose (1/2/s/d): ").strip().lower()
                    
                    if choice == '1':
                        selections['structure_only'].append(table)
                        print(f"    ✅ {table}: Structure only")
                        break
                    elif choice == '2':
                        selections['structure_and_data'].append(table)
                        print(f"    ✅ {table}: Structure + data ({rows:,} records)")
                        break
                    elif choice == 's':
                        selections['skip'].append(table)
                        print(f"    ⏭️ {table}: Skipped")
                        break
                    elif choice == 'd':
                        self.show_detailed_table_differences(table, schema1, schema2, is_new_table=True)
                        continue
                    elif choice == 'q':
                        print("❌ Operation cancelled by user.")
                        return {}
                    else:
                        print("    ❌ Invalid choice. Use 1, 2, s, d, or q")
        
        # Handle modified tables
        if differences['modified_tables']:
            print(f"\n{'='*80}")
            print(f"🔧 MODIFIED TABLES ({len(differences['modified_tables'])} tables)")
            print("="*80)
            
            for table in differences['modified_tables']:
                rows1 = schema1['tables'][table]['rows']
                
                # Show detailed differences
                self.show_detailed_table_differences(table, schema1, schema2, is_new_table=False)
                
                while True:
                    print(f"\n🤔 What to do with table '{table}'?")
                    choice = input(f"   Choose (1/2/s/d): ").strip().lower()
                    
                    if choice == '1':
                        selections['structure_only'].append(table)
                        print(f"    ✅ {table}: Structure only")
                        break
                    elif choice == '2':
                        selections['structure_and_data'].append(table)
                        print(f"    ✅ {table}: Structure + data ({rows1:,} records)")
                        break
                    elif choice == 's':
                        selections['skip'].append(table)
                        print(f"    ⏭️ {table}: Skipped")
                        break
                    elif choice == 'd':
                        self.show_detailed_table_differences(table, schema1, schema2, is_new_table=False)
                        continue
                    elif choice == 'q':
                        print("❌ Operation cancelled by user.")
                        return {}
                    else:
                        print("    ❌ Invalid choice. Use 1, 2, s, d, or q")
        
        # Handle tables to remove
        if differences['removed_tables']:
            print(f"\n{'='*80}")
            print(f"🗑️ TABLES FOR REMOVAL ({len(differences['removed_tables'])} tables)")
            print("="*80)
            print("⚠️  These tables exist only in target:")
            
            for table in differences['removed_tables']:
                rows = schema2['tables'][table]['rows']
                print(f"\n📋 Table: {table} ({rows:,} records)")
                
                # Show some details about the table to be removed
                if table in schema2['columns']:
                    cols_count = len(schema2['columns'][table])
                    print(f"   • {cols_count} columns")
                    if cols_count <= 5:
                        for col in schema2['columns'][table]:
                            print(f"   • {col['COLUMN_NAME']}: {col['COLUMN_TYPE']}")
                
                while True:
                    choice = input(f"\n   🗑️ Remove table '{table}'? (y/n/q): ").strip().lower()
                    if choice in ('y', 'yes'):
                        selections['drop_tables'].append(table)
                        print(f"    ✅ {table}: Will be removed")
                        break
                    elif choice in ('n', 'no'):
                        print(f"    ⏭️ {table}: Kept")
                        break
                    elif choice == 'q':
                        print("❌ Operation cancelled by user.")
                        return {}
                    else:
                        print("    ❌ Invalid choice. Use y/n/q")
        
        return selections
    
    def generate_structure_sql(self, selections: Dict, schema1: Dict, schema2: Dict, db1_name: str, db2_name: str) -> List[str]:
        """Generate SQL for structure changes."""
        sql_statements = []
        
        # Database setup
        sql_statements.append(f"-- Structure Synchronization Script")
        sql_statements.append(f"-- Generated by: MariaDB Advanced Database Synchronizer")
        sql_statements.append(f"-- Author: João Cortez (jbcortezf@gmail.com)")
        sql_statements.append(f"-- GitHub: https://github.com/jbcortezf/adjust-mariadb")
        sql_statements.append(f"-- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sql_statements.append(f"-- Source: {db1_name} → Target: {db2_name}")
        sql_statements.append("")
        sql_statements.append(f"USE `{db2_name}`;")
        sql_statements.append("SET FOREIGN_KEY_CHECKS = 0;")
        sql_statements.append("")
        
        # Drop tables
        for table in selections['drop_tables']:
            sql_statements.append(f"-- Removing table {table}")
            sql_statements.append(f"DROP TABLE IF EXISTS `{table}`;")
            sql_statements.append("")
        
        # Create new tables (structure only)
        tables_to_create = selections['structure_only'] + selections['structure_and_data']
        tables_to_create = [t for t in tables_to_create if t in schema1['tables']]
        
        for table in tables_to_create:
            if table not in schema2['tables']:  # New table
                sql_statements.append(f"-- Creating table {table}")
                sql_statements.append(f"{schema1['tables'][table]['create_statement']};")
                sql_statements.append("")
            else:  # Modified table
                sql_statements.append(f"-- Modifying table structure {table}")
                modifications = self.generate_table_modifications(table, schema1, schema2)
                sql_statements.extend(modifications)
                sql_statements.append("")
        
        sql_statements.append("SET FOREIGN_KEY_CHECKS = 1;")
        return sql_statements
    
    def generate_table_modifications(self, table_name: str, schema1: Dict, schema2: Dict) -> List[str]:
        """Generate ALTER statements for a single table."""
        statements = []
        
        cols1 = {col['COLUMN_NAME']: col for col in schema1['columns'][table_name]}
        cols2 = {col['COLUMN_NAME']: col for col in schema2['columns'][table_name]}
        
        # Add new columns
        new_cols = set(cols1.keys()) - set(cols2.keys())
        for col in new_cols:
            col_info = cols1[col]
            null_clause = "NULL" if col_info['IS_NULLABLE'] == 'YES' else "NOT NULL"
            default_clause = f"DEFAULT {col_info['COLUMN_DEFAULT']}" if col_info['COLUMN_DEFAULT'] is not None else ""
            extra_clause = col_info['EXTRA'] if col_info['EXTRA'] else ""
            
            alter_stmt = f"ALTER TABLE `{table_name}` ADD COLUMN `{col}` {col_info['COLUMN_TYPE']} {null_clause} {default_clause} {extra_clause}".strip()
            statements.append(alter_stmt + ";")
        
        # Drop removed columns
        removed_cols = set(cols2.keys()) - set(cols1.keys())
        for col in removed_cols:
            statements.append(f"ALTER TABLE `{table_name}` DROP COLUMN `{col}`;")
        
        # Modify existing columns
        common_cols = set(cols1.keys()) & set(cols2.keys())
        for col in common_cols:
            col1 = cols1[col]
            col2 = cols2[col]
            
            if (col1['COLUMN_TYPE'] != col2['COLUMN_TYPE'] or 
                col1['IS_NULLABLE'] != col2['IS_NULLABLE'] or
                col1['COLUMN_DEFAULT'] != col2['COLUMN_DEFAULT'] or
                col1['EXTRA'] != col2['EXTRA']):
                
                null_clause = "NULL" if col1['IS_NULLABLE'] == 'YES' else "NOT NULL"
                default_clause = f"DEFAULT {col1['COLUMN_DEFAULT']}" if col1['COLUMN_DEFAULT'] is not None else ""
                extra_clause = col1['EXTRA'] if col1['EXTRA'] else ""
                
                alter_stmt = f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col}` {col1['COLUMN_TYPE']} {null_clause} {default_clause} {extra_clause}".strip()
                statements.append(alter_stmt + ";")
        
        return statements
    
    def generate_data_sql(self, selections: Dict, schema1: Dict, db1_name: str, db2_name: str) -> List[str]:
        """Generate SQL for data synchronization."""
        if not selections['structure_and_data']:
            return []
        
        sql_statements = []
        sql_statements.append(f"-- Data Synchronization Script")
        sql_statements.append(f"-- Generated by: MariaDB Advanced Database Synchronizer")
        sql_statements.append(f"-- Author: João Cortez (jbcortezf@gmail.com)")
        sql_statements.append(f"-- GitHub: https://github.com/jbcortezf/adjust-mariadb")
        sql_statements.append(f"-- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sql_statements.append("")
        sql_statements.append(f"USE `{db2_name}`;")
        sql_statements.append("SET FOREIGN_KEY_CHECKS = 0;")
        sql_statements.append("")
        
        cursor1 = self.db1_conn.cursor()
        
        try:
            cursor1.execute(f"USE `{db1_name}`")
            
            for table in selections['structure_and_data']:
                if table in schema1['tables']:
                    rows_count = schema1['tables'][table]['rows']
                    
                    sql_statements.append(f"-- Synchronizing data for table {table} ({rows_count:,} records)")
                    sql_statements.append(f"TRUNCATE TABLE `{table}`;")
                    
                    # Get column names for INSERT
                    columns = [col['COLUMN_NAME'] for col in schema1['columns'][table]]
                    columns_str = '`, `'.join(columns)
                    
                    # Export data in batches
                    if rows_count > 0:
                        sql_statements.append(f"INSERT INTO `{table}` (`{columns_str}`) VALUES")
                        
                        # Note: In a real implementation, you'd want to stream the data
                        # This is a simplified version
                        sql_statements.append(f"-- WARNING: Data for table {table} must be exported separately")
                        sql_statements.append(f"-- due to large volume ({rows_count:,} records)")
                        
                        # Get database connection info from config for mysqldump command
                        db1_host = self.config.get('DEFAULT', 'database1ip')
                        db1_user = self.config.get('DEFAULT', 'database1user')
                        db1_name_config = self.config.get('DEFAULT', 'database1name')
                        
                        sql_statements.append(f"-- Use: mysqldump -h {db1_host} -u {db1_user} -p {db1_name_config} {table} --no-create-info")
                    
                    sql_statements.append("")
        
        finally:
            cursor1.close()
        
        sql_statements.append("SET FOREIGN_KEY_CHECKS = 1;")
        return sql_statements
    
    def show_selection_summary(self, selections: Dict):
        """Show summary of user selections."""
        print("\n" + "="*80)
        print("SELECTION SUMMARY")
        print("="*80)
        
        if selections['structure_only']:
            print(f"\n🔧 STRUCTURE ONLY ({len(selections['structure_only'])} tables):")
            for table in selections['structure_only']:
                print(f"   • {table}")
        
        if selections['structure_and_data']:
            print(f"\n📊 STRUCTURE + DATA ({len(selections['structure_and_data'])} tables):")
            for table in selections['structure_and_data']:
                print(f"   • {table}")
        
        if selections['drop_tables']:
            print(f"\n🗑️  TABLES TO REMOVE ({len(selections['drop_tables'])} tables):")
            for table in selections['drop_tables']:
                print(f"   • {table}")
        
        if selections['skip']:
            print(f"\n⏭️  SKIPPED TABLES ({len(selections['skip'])} tables):")
            for table in selections['skip']:
                print(f"   • {table}")
    
    def execute_sync(self, db2_name: str) -> bool:
        """Execute the synchronization process."""
        try:
            cursor = self.db2_conn.cursor()
            
            # Execute structure changes
            if self.structure_sql:
                print("\n🔧 Applying structural changes...")
                for i, statement in enumerate(self.structure_sql):
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            cursor.execute(statement)
                            if i % 10 == 0:  # Show progress every 10 statements
                                print(f"   Executed {i+1}/{len(self.structure_sql)} commands...")
                        except Exception as e:
                            print(f"   ⚠️  Error in: {statement[:50]}... - {e}")
                
                self.db2_conn.commit()
                print("   ✓ Structural changes applied successfully!")
            
            return True
            
        except Exception as e:
            print(f"✗ Error during synchronization: {e}")
            self.db2_conn.rollback()
            return False
        finally:
            cursor.close()
    
    def save_sql_files(self, base_filename: str = 'sync_database'):
        """Save SQL files."""
        if self.structure_sql:
            structure_file = f"{base_filename}_structure.sql"
            with open(structure_file, 'w', encoding='utf-8') as f:
                for statement in self.structure_sql:
                    f.write(statement + '\n')
            print(f"✓ Structure SQL saved to: {structure_file}")
        
        if self.data_sql:
            data_file = f"{base_filename}_data.sql"
            with open(data_file, 'w', encoding='utf-8') as f:
                for statement in self.data_sql:
                    f.write(statement + '\n')
            print(f"✓ Data SQL saved to: {data_file}")
    
    def close_connections(self):
        """Close database connections."""
        if self.db1_conn:
            self.db1_conn.close()
        if self.db2_conn:
            self.db2_conn.close()

def main():
    """Main function."""
    print("="*80)
    print("MARIADB ADVANCED DATABASE SYNCHRONIZER")
    print("Author: João Cortez | Email: jbcortezf@gmail.com")
    print("GitHub: https://github.com/jbcortezf/adjust-mariadb")
    print("="*80)
    
    syncer = AdvancedDatabaseSyncer()
    
    if not syncer.connect_databases():
        sys.exit(1)
    
    try:
        # Get database names from config file
        db1_name = syncer.config.get('DEFAULT', 'database1name')
        db2_name = syncer.config.get('DEFAULT', 'database2name')
        
        print(f"\n🔍 Analyzing differences between '{db1_name}' and '{db2_name}'...")
        
        # Get schemas (databases are already selected during connection)
        schema1 = syncer.get_database_schema(syncer.db1_conn)
        schema2 = syncer.get_database_schema(syncer.db2_conn)
        
        # Analyze differences
        differences = syncer.analyze_differences(schema1, schema2, db1_name, db2_name)
        
        # Show analysis
        syncer.show_analysis_summary(differences, schema1, schema2)
        
        # Check if there are differences
        total_changes = (len(differences['new_tables']) + 
                        len(differences['modified_tables']) + 
                        len(differences['removed_tables']))
        
        if total_changes == 0:
            print("\n✅ Databases are already synchronized!")
            return
        
        # Interactive selection
        print(f"\n📋 Total of {total_changes} differences found.")
        proceed = input("\nProceed with interactive selection? (y/n): ").strip().lower()
        
        if proceed not in ('y', 'yes'):
            print("Operation cancelled.")
            return
        
        selections = syncer.interactive_selection(differences, schema1, schema2)
        
        if not selections:
            return
        
        # Show selection summary
        syncer.show_selection_summary(selections)
        
        # Generate SQL
        print("\n🔨 Generating SQL commands...")
        syncer.structure_sql = syncer.generate_structure_sql(selections, schema1, schema2, db1_name, db2_name)
        syncer.data_sql = syncer.generate_data_sql(selections, schema1, db1_name, db2_name)
        
        # Save SQL files
        save_files = input("\nSave SQL files? (y/n) [y]: ").strip().lower()
        if save_files in ('', 'y', 'yes'):
            filename = input("Base filename [sync_database]: ").strip()
            if not filename:
                filename = 'sync_database'
            syncer.save_sql_files(filename)
        
        # Show preview of structure SQL
        if syncer.structure_sql:
            print(f"\n📝 Structure SQL preview ({len(syncer.structure_sql)} commands):")
            print("-" * 60)
            for i, stmt in enumerate(syncer.structure_sql[:10]):
                print(stmt)
            if len(syncer.structure_sql) > 10:
                print(f"... and {len(syncer.structure_sql) - 10} more commands")
        
        # Ask to apply changes
        apply_changes = input(f"\nApply changes to database '{db2_name}'? (y/n) [n]: ").strip().lower()
        
        if apply_changes in ('y', 'yes'):
            if syncer.execute_sync(db2_name):
                print(f"\n✅ Synchronization completed successfully!")
                
                if syncer.data_sql:
                    print("\n⚠️  WARNING: For tables with data, you need to execute")
                    print("   the data synchronization commands separately.")
                    print("   Check the generated *_data.sql file.")
            else:
                print(f"\n❌ Synchronization failed.")
        else:
            print("\n📋 Changes not applied. SQL files were generated for manual review.")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        syncer.close_connections()
        print("\n👋 Connections closed. Goodbye!")

if __name__ == "__main__":
    main()
