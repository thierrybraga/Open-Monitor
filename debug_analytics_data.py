#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debugar o problema de consumo de dados na página analytics
"""

import requests
import json
from datetime import datetime

def test_analytics_data_flow():
    """Testa o fluxo completo de dados da página analytics"""
    base_url = "http://localhost:5000"
    
    print("=== DEBUG: Análise do fluxo de dados da página Analytics ===")
    print(f"Timestamp: {datetime.now()}\n")
    
    # 1. Testar API de analytics diretamente
    print("1. Testando API /api/analytics/overview...")
    try:
        response = requests.get(f"{base_url}/api/analytics/overview", timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   Dados retornados pela API:")
            for key, value in data.items():
                print(f"     {key}: {value}")
            
            # Verificar se os dados são válidos
            expected_fields = ['total_cves', 'patched_cves', 'unpatched_cves', 
                             'active_threats', 'avg_cvss_score', 'avg_exploit_score', 
                             'patch_coverage']
            
            missing_fields = [field for field in expected_fields if field not in data]
            if missing_fields:
                print(f"   ⚠️  Campos ausentes: {missing_fields}")
            else:
                print("   ✅ Todos os campos esperados estão presentes")
                
            # Verificar se os valores são realistas
            if data.get('total_cves', 0) == 0:
                print("   ⚠️  Total de CVEs é 0 - possível problema no banco de dados")
            else:
                print(f"   ✅ Total de CVEs: {data.get('total_cves')}")
                
        else:
            print(f"   ❌ Erro na API: {response.status_code}")
            print(f"   Resposta: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Erro ao acessar API: {e}")
    
    print("\n" + "="*60)
    
    # 2. Testar acesso ao arquivo JavaScript
    print("2. Testando arquivo analytics.js...")
    try:
        response = requests.get(f"{base_url}/static/js/analytics.js", timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            js_content = response.text
            print(f"   Tamanho do arquivo: {len(js_content)} caracteres")
            
            # Verificar se contém as funções principais
            key_functions = ['AnalyticsManager', 'loadAnalyticsData', 'updateCards']
            for func in key_functions:
                if func in js_content:
                    print(f"   ✅ Função '{func}' encontrada")
                else:
                    print(f"   ⚠️  Função '{func}' não encontrada")
                    
            # Verificar se faz chamada para a API correta
            if '/api/analytics/overview' in js_content:
                print("   ✅ Chamada para API encontrada no JavaScript")
            else:
                print("   ⚠️  Chamada para API não encontrada no JavaScript")
                
        else:
            print(f"   ❌ Erro ao carregar JavaScript: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erro ao acessar JavaScript: {e}")
    
    print("\n" + "="*60)
    
    # 3. Testar página analytics (sem login)
    print("3. Testando página /analytics...")
    try:
        response = requests.get(f"{base_url}/analytics", timeout=10, allow_redirects=False)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 302:
            print("   ℹ️  Redirecionamento detectado (provavelmente para login)")
            location = response.headers.get('Location', 'N/A')
            print(f"   Redirecionando para: {location}")
        elif response.status_code == 200:
            print("   ✅ Página acessível")
            # Verificar se contém os elementos esperados
            content = response.text
            if 'analytics-cards' in content:
                print("   ✅ Container de cards encontrado")
            else:
                print("   ⚠️  Container de cards não encontrado")
        else:
            print(f"   ❌ Erro inesperado: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erro ao acessar página: {e}")
    
    print("\n" + "="*60)
    
    # 4. Verificar se há dados no banco
    print("4. Testando outras APIs para verificar dados no banco...")
    
    # Testar API de vulnerabilidades
    try:
        response = requests.get(f"{base_url}/api/vulnerabilities", timeout=10)
        print(f"   API Vulnerabilidades - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'vulnerabilities' in data:
                vuln_count = len(data['vulnerabilities'])
                print(f"   ✅ {vuln_count} vulnerabilidades encontradas")
            elif isinstance(data, list):
                print(f"   ✅ {len(data)} vulnerabilidades encontradas")
            else:
                print(f"   ⚠️  Formato de resposta inesperado: {type(data)}")
        else:
            print(f"   ⚠️  Erro na API de vulnerabilidades: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erro ao testar API de vulnerabilidades: {e}")
    
    print("\n" + "="*60)
    print("\n=== RESUMO DO DIAGNÓSTICO ===")
    print("Verifique os pontos marcados com ⚠️  ou ❌ acima.")
    print("Se a API retorna dados mas a página não os exibe, o problema")
    print("pode estar no JavaScript ou na autenticação da página.")
    print("\nPróximos passos sugeridos:")
    print("1. Verificar se há erros no console do navegador")
    print("2. Verificar se o usuário está logado ao acessar /analytics")
    print("3. Verificar se o JavaScript está sendo carregado corretamente")
    print("4. Verificar se há dados reais no banco de dados")

if __name__ == "__main__":
    test_analytics_data_flow()