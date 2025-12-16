import os
import sys
import json
from datetime import datetime


def ensure_path():
    # Garantir que o pacote 'app' seja importável
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(app_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def main():
    ensure_path()
    from app.app import create_app
    from app.extensions import db
    from sqlalchemy import text as sa_text
    from app.models.vendor import Vendor
    from app.models.product import Product
    from app.models.asset import Asset
    from app.models.asset_product import AssetProduct
    from app.services.vulnerability_service import VulnerabilityService

    app = create_app()
    metrics = {
        'timestamp': datetime.utcnow().isoformat(),
        'scenarios': [],
    }

    with app.app_context():
        # Verificar existência da tabela asset_products (compatível com endpoint)
        try:
            has_asset_products_table = bool(
                db.session.execute(
                    sa_text("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_products'")
                ).scalar()
            )
        except Exception:
            has_asset_products_table = True  # fallback conservador

        if not has_asset_products_table:
            metrics['error'] = 'Tabela asset_products ausente; execute as migrações antes da verificação.'
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
            return

        # Preparar vendors, products e assets para testes
        vendor_a = db.session.query(Vendor).filter_by(name='VendorA').first()
        if not vendor_a:
            vendor_a = Vendor(name='VendorA')
            db.session.add(vendor_a)
            db.session.flush()

        vendor_b = db.session.query(Vendor).filter_by(name='VendorB').first()
        if not vendor_b:
            vendor_b = Vendor(name='VendorB')
            db.session.add(vendor_b)
            db.session.flush()

        prod_a = (
            db.session.query(Product)
            .filter_by(name='Router X', vendor_id=vendor_a.id)
            .first()
        )
        if not prod_a:
            prod_a = Product(name='Router X', vendor_id=vendor_a.id, type='Router')
            db.session.add(prod_a)
            db.session.flush()

        prod_b = (
            db.session.query(Product)
            .filter_by(name='Switch Y', vendor_id=vendor_b.id)
            .first()
        )
        if not prod_b:
            prod_b = Product(name='Switch Y', vendor_id=vendor_b.id, type='Switch')
            db.session.add(prod_b)
            db.session.flush()

        # Asset com vendor (VendorA)
        asset_with_vendor = (
            db.session.query(Asset)
            .filter_by(ip_address='10.254.1.1', vendor_id=vendor_a.id)
            .first()
        )
        if not asset_with_vendor:
            asset_with_vendor = Asset(
                name='Asset Verif A',
                ip_address='10.254.1.1',
                status='active',
                vendor_id=vendor_a.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(asset_with_vendor)
            try:
                db.session.flush()
            except Exception:
                db.session.rollback()
                # Recuperar existente caso conflito por IP
                asset_with_vendor = (
                    db.session.query(Asset)
                    .filter_by(ip_address='10.254.1.1')
                    .first()
                )
                if asset_with_vendor and not asset_with_vendor.vendor_id:
                    # Ajustar vendor_id se estiver ausente
                    asset_with_vendor.vendor_id = vendor_a.id
                    db.session.commit()

        # Asset sem vendor
        asset_without_vendor = (
            db.session.query(Asset)
            .filter_by(ip_address='10.254.1.2')
            .first()
        )
        if not asset_without_vendor:
            asset_without_vendor = Asset(
                name='Asset Verif B',
                ip_address='10.254.1.2',
                status='active',
                vendor_id=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(asset_without_vendor)
            try:
                db.session.flush()
            except Exception:
                db.session.rollback()
                asset_without_vendor = (
                    db.session.query(Asset)
                    .filter_by(ip_address='10.254.1.2')
                    .first()
                )

        db.session.commit()

        # Cenário 1: asset com vendor (VendorA) vinculando produto do mesmo vendor (prod_a)
        scenario1 = {'name': 'asset_vendor_match', 'asset_id': asset_with_vendor.id, 'product_id': prod_a.id}
        try:
            link = (
                db.session.query(AssetProduct)
                .filter_by(asset_id=asset_with_vendor.id, product_id=prod_a.id)
                .first()
            )
            if not link:
                link = AssetProduct(asset_id=asset_with_vendor.id, product_id=prod_a.id)
                db.session.add(link)
                db.session.commit()
            scenario1['status'] = 'success'
            scenario1['message'] = 'Produto vinculado com vendor correspondente.'
        except Exception as e:
            db.session.rollback()
            scenario1['status'] = 'error'
            scenario1['message'] = f'Falha ao vincular: {e}'
        metrics['scenarios'].append(scenario1)

        # Cenário 2: asset com vendor (VendorA) tentando vincular produto de vendor diferente (prod_b)
        scenario2 = {'name': 'asset_vendor_mismatch', 'asset_id': asset_with_vendor.id, 'product_id': prod_b.id}
        try:
            if asset_with_vendor.vendor_id and prod_b.vendor_id != asset_with_vendor.vendor_id:
                scenario2['status'] = 'error'
                scenario2['message'] = 'Produto não pertence ao fornecedor do ativo.'
            else:
                # Não deve ocorrer, mas manter a lógica completa
                link = (
                    db.session.query(AssetProduct)
                    .filter_by(asset_id=asset_with_vendor.id, product_id=prod_b.id)
                    .first()
                )
                if not link:
                    link = AssetProduct(asset_id=asset_with_vendor.id, product_id=prod_b.id)
                    db.session.add(link)
                    db.session.commit()
                scenario2['status'] = 'success'
                scenario2['message'] = 'Produto vinculado (sem restrição de vendor).'
        except Exception as e:
            db.session.rollback()
            scenario2['status'] = 'error'
            scenario2['message'] = f'Falha ao vincular: {e}'
        metrics['scenarios'].append(scenario2)

        # Cenário 3: asset sem vendor vinculando produto de qualquer vendor (prod_b)
        scenario3 = {'name': 'asset_without_vendor', 'asset_id': asset_without_vendor.id, 'product_id': prod_b.id}
        try:
            link = (
                db.session.query(AssetProduct)
                .filter_by(asset_id=asset_without_vendor.id, product_id=prod_b.id)
                .first()
            )
            if not link:
                link = AssetProduct(asset_id=asset_without_vendor.id, product_id=prod_b.id)
                db.session.add(link)
                db.session.commit()
            scenario3['status'] = 'success'
            scenario3['message'] = 'Produto vinculado a ativo sem vendor.'
        except Exception as e:
            db.session.rollback()
            scenario3['status'] = 'error'
            scenario3['message'] = f'Falha ao vincular: {e}'
        metrics['scenarios'].append(scenario3)

        # Sincronizar CVEs para os ativos e registrar métricas de criação
        try:
            vuln_service = VulnerabilityService(db.session)
            created_for_asset_a = vuln_service.sync_asset_vulnerabilities_for_asset(asset_with_vendor.id)
            created_for_asset_b = vuln_service.sync_asset_vulnerabilities_for_asset(asset_without_vendor.id)
            metrics['sync'] = {
                'asset_with_vendor_created_links': created_for_asset_a,
                'asset_without_vendor_created_links': created_for_asset_b,
            }
        except Exception as e:
            metrics['sync_error'] = f'Falha ao sincronizar vulnerabilidades: {e}'

        # Persistir métricas em arquivo JSON
        out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'temp')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'verify_asset_actions.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()