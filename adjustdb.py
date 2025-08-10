#!/usr/bin/env python3
"""
MariaDB Advanced Schema & Data Synchronization Script

This script compares two MariaDB databases and allows granular control
over synchronization of structure and/or data for each table.

Requirements:
- pymysql or mysql-connector-python
- databases.ini file with connection parameters
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
            
            print("✓ Conectado com sucesso a ambos os bancos de dados")
            print(f"  - Origem: {self.config.get('DEFAULT', 'database1name')} em {self.config.get('DEFAULT', 'database1ip')}")
            print(f"  - Destino: {self.config.get('DEFAULT', 'database2name')} em {self.config.get('DEFAULT', 'database2ip')}")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao conectar aos bancos de dados: {e}")
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
                    print("Nenhum banco de dados selecionado")
                    return schema
            
            print(f"📊 Analisando banco: {current_db}")
            
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
            print(f"   Encontradas {len(tables_info)} tabelas")
            
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
                
                # Get foreign keys (usando REFERENTIAL_CONSTRAINTS para obter regras)
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
                    # Fallback para versões mais antigas do MariaDB
                    print(f"   ⚠️ Aviso: Não foi possível obter foreign keys detalhadas para {table_name}: {fk_error}")
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
            print(f"Erro ao extrair esquema: {e}")
            
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
        
        print(f"\n🔍 Comparação detalhada:")
        print(f"   Banco origem ({db1_name}): {len(tables1)} tabelas")
        print(f"   Banco destino ({db2_name}): {len(tables2)} tabelas")
        
        # New tables (exist in source but not in target)
        differences['new_tables'] = sorted(list(tables1 - tables2))
        
        # Removed tables (exist in target but not in source)
        differences['removed_tables'] = sorted(list(tables2 - tables1))
        
        # Check common tables for modifications
        common_tables = tables1 & tables2
        print(f"   Tabelas em comum: {len(common_tables)}")
        
        for table in sorted(common_tables):
            if self.table_has_differences(table, schema1, schema2):
                differences['modified_tables'].append(table)
            else:
                differences['identical_tables'].append(table)
        
        print(f"   → Novas: {len(differences['new_tables'])}")
        print(f"   → Removidas: {len(differences['removed_tables'])}")
        print(f"   → Modificadas: {len(differences['modified_tables'])}")
        print(f"   → Idênticas: {len(differences['identical_tables'])}")
        
        return differences
    
    def table_has_differences(self, table_name: str, schema1: Dict, schema2: Dict) -> bool:
        """Check if a table has structural differences between schemas."""
        # Debug: vamos ver se há problemas na comparação
        if table_name not in schema1['columns'] or table_name not in schema2['columns']:
            print(f"   ⚠️ Tabela {table_name}: dados de colunas ausentes")
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
                print(f"   🔍 {table_name}: Diferenças nas colunas detectadas")
                if new_cols:
                    print(f"      + Novas: {list(new_cols)[:3]}{'...' if len(new_cols) > 3 else ''}")
                if removed_cols:
                    print(f"      - Removidas: {list(removed_cols)[:3]}{'...' if len(removed_cols) > 3 else ''}")
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
            print(f"   🔍 {table_name}: Definições diferentes em {len(different_cols)} colunas")
            print(f"      Colunas: {different_cols[:3]}{'...' if len(different_cols) > 3 else ''}")
            return True
        
        return False
    
    def show_analysis_summary(self, differences: Dict, schema1: Dict, schema2: Dict):
        """Display a comprehensive analysis of differences."""
        print("\n" + "="*80)
        print("ANÁLISE DE DIFERENÇAS ENTRE OS BANCOS DE DADOS")
        print("="*80)
        
        if differences['new_tables']:
            print(f"\n📋 TABELAS NOVAS ({len(differences['new_tables'])} tabelas):")
            print("   (Existem apenas no banco origem)")
            for table in differences['new_tables']:
                rows = schema1['tables'][table]['rows']
                print(f"   • {table} ({rows:,} registros)")
        
        if differences['removed_tables']:
            print(f"\n🗑️  TABELAS A REMOVER ({len(differences['removed_tables'])} tabelas):")
            print("   (Existem apenas no banco destino)")
            for table in differences['removed_tables']:
                rows = schema2['tables'][table]['rows']
                print(f"   • {table} ({rows:,} registros)")
        
        if differences['modified_tables']:
            print(f"\n🔧 TABELAS MODIFICADAS ({len(differences['modified_tables'])} tabelas):")
            print("   (Diferenças estruturais detectadas)")
            for table in differences['modified_tables']:
                rows1 = schema1['tables'][table]['rows']
                rows2 = schema2['tables'][table]['rows']
                print(f"   • {table} (origem: {rows1:,} → destino: {rows2:,} registros)")
                
                # Show specific differences
                self.show_table_differences(table, schema1, schema2)
        
        if differences['identical_tables']:
            print(f"\n✅ TABELAS IDÊNTICAS ({len(differences['identical_tables'])} tabelas):")
            for i, table in enumerate(differences['identical_tables']):
                if i < 10:  # Show first 10
                    print(f"   • {table}")
                elif i == 10:
                    print(f"   • ... e mais {len(differences['identical_tables']) - 10} tabelas")
                    break
    
    def show_table_differences(self, table_name: str, schema1: Dict, schema2: Dict):
        """Show specific differences for a table."""
        cols1 = {col['COLUMN_NAME']: col for col in schema1['columns'][table_name]}
        cols2 = {col['COLUMN_NAME']: col for col in schema2['columns'][table_name]}
        
        # New columns
        new_cols = set(cols1.keys()) - set(cols2.keys())
        if new_cols:
            print(f"     → Novas colunas: {', '.join(sorted(new_cols))}")
        
        # Removed columns
        removed_cols = set(cols2.keys()) - set(cols1.keys())
        if removed_cols:
            print(f"     → Colunas removidas: {', '.join(sorted(removed_cols))}")
        
        # Modified columns
        common_cols = set(cols1.keys()) & set(cols2.keys())
        modified_cols = []
        for col_name in common_cols:
            if (cols1[col_name]['COLUMN_TYPE'] != cols2[col_name]['COLUMN_TYPE'] or
                cols1[col_name]['IS_NULLABLE'] != cols2[col_name]['IS_NULLABLE'] or
                cols1[col_name]['COLUMN_DEFAULT'] != cols2[col_name]['COLUMN_DEFAULT']):
                modified_cols.append(col_name)
        
        if modified_cols:
            print(f"     → Colunas modificadas: {', '.join(sorted(modified_cols))}")
    
    def show_detailed_table_differences(self, table_name: str, schema1: Dict, schema2: Dict, is_new_table: bool = False):
        """Show detailed structural differences for a specific table."""
        print(f"\n{'='*60}")
        print(f"📋 DETALHES DA TABELA: {table_name}")
        print(f"{'='*60}")
        
        if is_new_table:
            print("🆕 TABELA NOVA (não existe no destino)")
            print(f"   Engine: {schema1['tables'][table_name].get('engine', 'N/A')}")
            print(f"   Registros: {schema1['tables'][table_name].get('rows', 0):,}")
            
            # Show columns structure
            columns = schema1['columns'][table_name]
            print(f"\n📋 ESTRUTURA ({len(columns)} colunas):")
            for col in columns[:10]:  # Show first 10 columns
                nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                default = f"DEFAULT {col['COLUMN_DEFAULT']}" if col['COLUMN_DEFAULT'] else ""
                extra = col['EXTRA'] if col['EXTRA'] else ""
                print(f"   • {col['COLUMN_NAME']}: {col['COLUMN_TYPE']} {nullable} {default} {extra}".strip())
            
            if len(columns) > 10:
                print(f"   ... e mais {len(columns) - 10} colunas")
            return
        
        # For existing tables, show detailed differences
        cols1 = {col['COLUMN_NAME']: col for col in schema1['columns'][table_name]}
        cols2 = {col['COLUMN_NAME']: col for col in schema2['columns'][table_name]}
        
        rows1 = schema1['tables'][table_name].get('rows', 0)
        rows2 = schema2['tables'][table_name].get('rows', 0)
        
        print(f"📊 REGISTROS: Origem {rows1:,} → Destino {rows2:,}")
        
        # New columns (in source but not in target)
        new_cols = set(cols1.keys()) - set(cols2.keys())
        if new_cols:
            print(f"\n➕ COLUNAS NOVAS ({len(new_cols)}):")
            for col_name in sorted(new_cols):
                col = cols1[col_name]
                nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                default = f"DEFAULT {col['COLUMN_DEFAULT']}" if col['COLUMN_DEFAULT'] else ""
                extra = col['EXTRA'] if col['EXTRA'] else ""
                print(f"   • {col_name}: {col['COLUMN_TYPE']} {nullable} {default} {extra}".strip())
        
        # Removed columns (in target but not in source)
        removed_cols = set(cols2.keys()) - set(cols1.keys())
        if removed_cols:
            print(f"\n➖ COLUNAS REMOVIDAS ({len(removed_cols)}):")
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
                differences.append(f"Tipo: {col2['COLUMN_TYPE']} → {col1['COLUMN_TYPE']}")
            
            if col1['IS_NULLABLE'] != col2['IS_NULLABLE']:
                old_null = "NULL" if col2['IS_NULLABLE'] == 'YES' else "NOT NULL"
                new_null = "NULL" if col1['IS_NULLABLE'] == 'YES' else "NOT NULL"
                differences.append(f"Nulável: {old_null} → {new_null}")
            
            if str(col1['COLUMN_DEFAULT']) != str(col2['COLUMN_DEFAULT']):
                old_default = col2['COLUMN_DEFAULT'] or 'NULL'
                new_default = col1['COLUMN_DEFAULT'] or 'NULL'
                differences.append(f"Padrão: {old_default} → {new_default}")
            
            if col1['EXTRA'] != col2['EXTRA']:
                old_extra = col2['EXTRA'] or '(nenhum)'
                new_extra = col1['EXTRA'] or '(nenhum)'
                differences.append(f"Extra: {old_extra} → {new_extra}")
            
            if differences:
                modified_cols.append((col_name, differences))
        
        if modified_cols:
            print(f"\n🔧 COLUNAS MODIFICADAS ({len(modified_cols)}):")
            for col_name, differences in modified_cols:
                print(f"   • {col_name}:")
                for diff in differences:
                    print(f"     - {diff}")
        
        # Show indexes differences if any
        self.show_index_differences(table_name, schema1, schema2)
        
        if not new_cols and not removed_cols and not modified_cols:
            print("\n✅ Estruturas idênticas (diferença apenas nos dados)")

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
            print(f"\n🔑 NOVOS ÍNDICES ({len(new_indexes)}):")
            for idx_name in sorted(new_indexes):
                cols = ', '.join(idx1_dict[idx_name])
                print(f"   • {idx_name}: ({cols})")
        
        if removed_indexes:
            print(f"\n🗑️ ÍNDICES REMOVIDOS ({len(removed_indexes)}):")
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
        print("SELEÇÃO INTERATIVA DE SINCRONIZAÇÃO")
        print("="*80)
        print("Opções:")
        print("  1 - Apenas estrutura")
        print("  2 - Estrutura + dados")
        print("  s - Pular esta tabela")
        print("  d - Ver detalhes da tabela novamente")
        print("  q - Sair")
        
        # Handle new tables
        if differences['new_tables']:
            print(f"\n{'='*80}")
            print(f"📋 TABELAS NOVAS ({len(differences['new_tables'])} tabelas)")
            print("="*80)
            
            for i, table in enumerate(differences['new_tables']):
                rows = schema1['tables'][table]['rows']
                
                # Show detailed differences
                self.show_detailed_table_differences(table, schema1, schema2, is_new_table=True)
                
                while True:
                    print(f"\n🤔 O que fazer com a tabela '{table}'?")
                    choice = input(f"   Escolha (1/2/s/d): ").strip().lower()
                    
                    if choice == '1':
                        selections['structure_only'].append(table)
                        print(f"    ✅ {table}: Apenas estrutura")
                        break
                    elif choice == '2':
                        selections['structure_and_data'].append(table)
                        print(f"    ✅ {table}: Estrutura + dados ({rows:,} registros)")
                        break
                    elif choice == 's':
                        selections['skip'].append(table)
                        print(f"    ⏭️ {table}: Pulado")
                        break
                    elif choice == 'd':
                        self.show_detailed_table_differences(table, schema1, schema2, is_new_table=True)
                        continue
                    elif choice == 'q':
                        print("❌ Operação cancelada pelo usuário.")
                        return {}
                    else:
                        print("    ❌ Escolha inválida. Use 1, 2, s, d, ou q")
        
        # Handle modified tables
        if differences['modified_tables']:
            print(f"\n{'='*80}")
            print(f"🔧 TABELAS MODIFICADAS ({len(differences['modified_tables'])} tabelas)")
            print("="*80)
            
            for table in differences['modified_tables']:
                rows1 = schema1['tables'][table]['rows']
                
                # Show detailed differences
                self.show_detailed_table_differences(table, schema1, schema2, is_new_table=False)
                
                while True:
                    print(f"\n🤔 O que fazer com a tabela '{table}'?")
                    choice = input(f"   Escolha (1/2/s/d): ").strip().lower()
                    
                    if choice == '1':
                        selections['structure_only'].append(table)
                        print(f"    ✅ {table}: Apenas estrutura")
                        break
                    elif choice == '2':
                        selections['structure_and_data'].append(table)
                        print(f"    ✅ {table}: Estrutura + dados ({rows1:,} registros)")
                        break
                    elif choice == 's':
                        selections['skip'].append(table)
                        print(f"    ⏭️ {table}: Pulado")
                        break
                    elif choice == 'd':
                        self.show_detailed_table_differences(table, schema1, schema2, is_new_table=False)
                        continue
                    elif choice == 'q':
                        print("❌ Operação cancelada pelo usuário.")
                        return {}
                    else:
                        print("    ❌ Escolha inválida. Use 1, 2, s, d, ou q")
        
        # Handle tables to remove
        if differences['removed_tables']:
            print(f"\n{'='*80}")
            print(f"🗑️ TABELAS PARA REMOÇÃO ({len(differences['removed_tables'])} tabelas)")
            print("="*80)
            print("⚠️  Estas tabelas existem apenas no destino:")
            
            for table in differences['removed_tables']:
                rows = schema2['tables'][table]['rows']
                print(f"\n📋 Tabela: {table} ({rows:,} registros)")
                
                # Show some details about the table to be removed
                if table in schema2['columns']:
                    cols_count = len(schema2['columns'][table])
                    print(f"   • {cols_count} colunas")
                    if cols_count <= 5:
                        for col in schema2['columns'][table]:
                            print(f"   • {col['COLUMN_NAME']}: {col['COLUMN_TYPE']}")
                
                while True:
                    choice = input(f"\n   🗑️ Remover tabela '{table}'? (y/n/q): ").strip().lower()
                    if choice in ('y', 'yes', 'sim', 's'):
                        selections['drop_tables'].append(table)
                        print(f"    ✅ {table}: Será removida")
                        break
                    elif choice in ('n', 'no', 'não'):
                        print(f"    ⏭️ {table}: Mantida")
                        break
                    elif choice == 'q':
                        print("❌ Operação cancelada pelo usuário.")
                        return {}
                    else:
                        print("    ❌ Escolha inválida. Use y/n/q")
        
        return selections
    
    def generate_structure_sql(self, selections: Dict, schema1: Dict, schema2: Dict, db1_name: str, db2_name: str) -> List[str]:
        """Generate SQL for structure changes."""
        sql_statements = []
        
        # Database setup
        sql_statements.append(f"-- Script de Sincronização de Estrutura")
        sql_statements.append(f"-- Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sql_statements.append(f"-- Origem: {db1_name} → Destino: {db2_name}")
        sql_statements.append("")
        sql_statements.append(f"USE `{db2_name}`;")
        sql_statements.append("SET FOREIGN_KEY_CHECKS = 0;")
        sql_statements.append("")
        
        # Drop tables
        for table in selections['drop_tables']:
            sql_statements.append(f"-- Removendo tabela {table}")
            sql_statements.append(f"DROP TABLE IF EXISTS `{table}`;")
            sql_statements.append("")
        
        # Create new tables (structure only)
        tables_to_create = selections['structure_only'] + selections['structure_and_data']
        tables_to_create = [t for t in tables_to_create if t in schema1['tables']]
        
        for table in tables_to_create:
            if table not in schema2['tables']:  # New table
                sql_statements.append(f"-- Criando tabela {table}")
                sql_statements.append(f"{schema1['tables'][table]['create_statement']};")
                sql_statements.append("")
            else:  # Modified table
                sql_statements.append(f"-- Modificando estrutura da tabela {table}")
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
        sql_statements.append(f"-- Script de Sincronização de Dados")
        sql_statements.append(f"-- Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
                    
                    sql_statements.append(f"-- Sincronizando dados da tabela {table} ({rows_count:,} registros)")
                    sql_statements.append(f"TRUNCATE TABLE `{table}`;")
                    
                    # Get column names for INSERT
                    columns = [col['COLUMN_NAME'] for col in schema1['columns'][table]]
                    columns_str = '`, `'.join(columns)
                    
                    # Export data in batches
                    if rows_count > 0:
                        sql_statements.append(f"INSERT INTO `{table}` (`{columns_str}`) VALUES")
                        
                        # Note: In a real implementation, you'd want to stream the data
                        # This is a simplified version
                        sql_statements.append(f"-- ATENÇÃO: Dados da tabela {table} devem ser exportados separadamente")
                        sql_statements.append(f"-- devido ao grande volume ({rows_count:,} registros)")
                        
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
        print("RESUMO DAS SELEÇÕES")
        print("="*80)
        
        if selections['structure_only']:
            print(f"\n🔧 APENAS ESTRUTURA ({len(selections['structure_only'])} tabelas):")
            for table in selections['structure_only']:
                print(f"   • {table}")
        
        if selections['structure_and_data']:
            print(f"\n📊 ESTRUTURA + DADOS ({len(selections['structure_and_data'])} tabelas):")
            for table in selections['structure_and_data']:
                print(f"   • {table}")
        
        if selections['drop_tables']:
            print(f"\n🗑️  TABELAS A REMOVER ({len(selections['drop_tables'])} tabelas):")
            for table in selections['drop_tables']:
                print(f"   • {table}")
        
        if selections['skip']:
            print(f"\n⏭️  TABELAS PULADAS ({len(selections['skip'])} tabelas):")
            for table in selections['skip']:
                print(f"   • {table}")
    
    def execute_sync(self, db2_name: str) -> bool:
        """Execute the synchronization process."""
        try:
            cursor = self.db2_conn.cursor()
            
            # Execute structure changes
            if self.structure_sql:
                print("\n🔧 Aplicando mudanças estruturais...")
                for i, statement in enumerate(self.structure_sql):
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            cursor.execute(statement)
                            if i % 10 == 0:  # Show progress every 10 statements
                                print(f"   Executado {i+1}/{len(self.structure_sql)} comandos...")
                        except Exception as e:
                            print(f"   ⚠️  Erro em: {statement[:50]}... - {e}")
                
                self.db2_conn.commit()
                print("   ✓ Mudanças estruturais aplicadas com sucesso!")
            
            return True
            
        except Exception as e:
            print(f"✗ Erro durante a sincronização: {e}")
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
            print(f"✓ SQL de estrutura salvo em: {structure_file}")
        
        if self.data_sql:
            data_file = f"{base_filename}_data.sql"
            with open(data_file, 'w', encoding='utf-8') as f:
                for statement in self.data_sql:
                    f.write(statement + '\n')
            print(f"✓ SQL de dados salvo em: {data_file}")
    
    def close_connections(self):
        """Close database connections."""
        if self.db1_conn:
            self.db1_conn.close()
        if self.db2_conn:
            self.db2_conn.close()

def main():
    """Main function."""
    print("="*80)
    print("SINCRONIZADOR AVANÇADO DE BANCOS DE DADOS MARIADB")
    print("="*80)
    
    syncer = AdvancedDatabaseSyncer()
    
    if not syncer.connect_databases():
        sys.exit(1)
    
    try:
        # Get database names from config file
        db1_name = syncer.config.get('DEFAULT', 'database1name')
        db2_name = syncer.config.get('DEFAULT', 'database2name')
        
        print(f"\n🔍 Analisando diferenças entre '{db1_name}' e '{db2_name}'...")
        
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
            print("\n✅ Os bancos de dados já estão sincronizados!")
            return
        
        # Interactive selection
        print(f"\n📋 Total de {total_changes} diferenças encontradas.")
        proceed = input("\nDeseja prosseguir com a seleção interativa? (s/n): ").strip().lower()
        
        if proceed not in ('s', 'sim', 'y', 'yes'):
            print("Operação cancelada.")
            return
        
        selections = syncer.interactive_selection(differences, schema1, schema2)
        
        if not selections:
            return
        
        # Show selection summary
        syncer.show_selection_summary(selections)
        
        # Generate SQL
        print("\n🔨 Gerando comandos SQL...")
        syncer.structure_sql = syncer.generate_structure_sql(selections, schema1, schema2, db1_name, db2_name)
        syncer.data_sql = syncer.generate_data_sql(selections, schema1, db1_name, db2_name)
        
        # Save SQL files
        save_files = input("\nSalvar arquivos SQL? (s/n) [s]: ").strip().lower()
        if save_files in ('', 's', 'sim', 'y', 'yes'):
            filename = input("Nome base dos arquivos [sync_database]: ").strip()
            if not filename:
                filename = 'sync_database'
            syncer.save_sql_files(filename)
        
        # Show preview of structure SQL
        if syncer.structure_sql:
            print(f"\n📝 Preview do SQL de estrutura ({len(syncer.structure_sql)} comandos):")
            print("-" * 60)
            for i, stmt in enumerate(syncer.structure_sql[:10]):
                print(stmt)
            if len(syncer.structure_sql) > 10:
                print(f"... e mais {len(syncer.structure_sql) - 10} comandos")
        
        # Ask to apply changes
        apply_changes = input(f"\nAplicar mudanças no banco '{db2_name}'? (s/n) [n]: ").strip().lower()
        
        if apply_changes in ('s', 'sim', 'y', 'yes'):
            if syncer.execute_sync(db2_name):
                print(f"\n✅ Sincronização concluída com sucesso!")
                
                if syncer.data_sql:
                    print("\n⚠️  ATENÇÃO: Para tabelas com dados, você precisa executar")
                    print("   os comandos de sincronização de dados separadamente.")
                    print("   Verifique o arquivo *_data.sql gerado.")
            else:
                print(f"\n❌ Falha na sincronização.")
        else:
            print("\n📋 Mudanças não aplicadas. Arquivos SQL foram gerados para revisão manual.")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro durante a execução: {e}")
        import traceback
        traceback.print_exc()
    finally:
        syncer.close_connections()
        print("\n👋 Conexões fechadas. Até logo!")

if __name__ == "__main__":
    main()
