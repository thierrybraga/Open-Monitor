import os
import sys
import logging
import bcrypt

# Garantir que o diretório raiz do projeto esteja no sys.path ao executar a partir de 'scripts/'
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from app.extensions.db import db
from app.models.asset import Asset
from app.models.user import User
from app.models.vendor import Vendor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ASSETS_TO_SEED = [
    {"name": "Firewall Fortigate 30E", "ip_address": "10.0.0.30"},
    {"name": "Firewall Fortigate 40F", "ip_address": "10.0.0.40"},
    {"name": "Switch Cisco", "ip_address": "10.0.0.50"},
    {"name": "Firewall Palo Alto", "ip_address": "10.0.0.60"},
    {"name": "Servidor Windows Server", "ip_address": "10.0.0.70"},
    {"name": "Access Point Ruckus", "ip_address": "10.0.0.80"},
    {"name": "Roteador Mikrotik", "ip_address": "10.0.0.90"},
]

VENDORS_TO_SEED = [
    "Fortinet",
    "Cisco",
    "Palo Alto Networks",
    "Ruckus",
    "MikroTik",
    "Microsoft",
]


def get_or_create_admin() -> User:
    """Cria (se necessário) e retorna o usuário admin com senha 'admin@teste'."""
    admin = User.query.filter_by(username='admin').first()
    if admin:
        logging.info(f"Usuário admin já existe: id={admin.id} username={admin.username}")
        return admin

    # Criar admin com email válido
    admin = User(username='admin', email='admin@example.com')
    admin.is_admin = True
    admin.is_active = True
    # Definir senha usando o método do modelo (valida e aplica bcrypt)
    admin.set_password('admin@teste')
    db.session.add(admin)
    try:
        db.session.commit()
        logging.info(f"Usuário admin criado: id={admin.id} username={admin.username}")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar usuário admin: {e}")
        raise
    return admin


def get_or_create_vendor(name: str):
    """Obtém ou cria um Vendor por nome (case-insensitive)."""
    if not name:
        return None
    v = Vendor.query.filter(db.func.lower(Vendor.name) == name.lower()).first()
    if v:
        return v
    v = Vendor(name=name)
    db.session.add(v)
    try:
        db.session.commit()
        logging.info(f"Vendor criado: id={v.id} name={v.name}")
        return v
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar vendor '{name}': {e}")
        return None


def seed_vendors():
    """Cria rapidamente alguns fornecedores comuns."""
    for name in VENDORS_TO_SEED:
        get_or_create_vendor(name)


def pick_vendor_name_for_asset(asset_name: str):
    """Retorna um nome de fornecedor com base em palavras-chave do nome do ativo."""
    if not asset_name:
        return None
    n = asset_name.lower()
    keyword_map = {
        'fortigate': 'Fortinet',
        'fortinet': 'Fortinet',
        'cisco': 'Cisco',
        'palo alto': 'Palo Alto Networks',
        'ruckus': 'Ruckus',
        'mikrotik': 'MikroTik',
        'windows server': 'Microsoft',
        'microsoft': 'Microsoft',
    }
    for kw, vendor_name in keyword_map.items():
        if kw in n:
            return vendor_name
    return None


def seed_assets():
    admin = get_or_create_admin()
    seed_vendors()
    created_count = 0
    updated_count = 0
    vendor_linked_new = 0
    vendor_linked_existing = 0
    for data in ASSETS_TO_SEED:
        existing = Asset.query.filter_by(ip_address=data["ip_address"]).first()
        vendor_name = pick_vendor_name_for_asset(data.get("name"))
        vendor_obj = get_or_create_vendor(vendor_name) if vendor_name else None
        vendor_id = vendor_obj.id if vendor_obj else None

        if existing:
            # Atualizar owner para admin se necessário
            changed = False
            if existing.owner_id != admin.id:
                existing.owner_id = admin.id
                changed = True
            # Associar vendor se ausente
            if existing.vendor_id is None and vendor_id is not None:
                existing.vendor_id = vendor_id
                vendor_linked_existing += 1
                changed = True
            if changed:
                try:
                    db.session.commit()
                    logging.info(
                        f"Atualizado ativo: {existing} -> owner_id={existing.owner_id} vendor_id={existing.vendor_id}"
                    )
                    updated_count += 1
                except Exception as e:
                    db.session.rollback()
                    logging.error(
                        f"Erro ao atualizar ativo {existing.name} ({existing.ip_address}): {e}"
                    )
            else:
                logging.info(
                    f"Ativo com IP {data['ip_address']} já pertence ao admin e possui vendor_id={existing.vendor_id}. Ignorando."
                )
            continue

        asset = Asset(
            name=data["name"],
            ip_address=data["ip_address"],
            status="active",
            owner_id=admin.id,
            vendor_id=vendor_id,
        )
        db.session.add(asset)
        try:
            db.session.commit()
            logging.info(
                f"Cadastrado: {asset} (vendor_id={asset.vendor_id if vendor_id else 'none'})"
            )
            created_count += 1
            if vendor_id:
                vendor_linked_new += 1
        except Exception as e:
            db.session.rollback()
            logging.error(
                f"Erro ao cadastrar {data['name']} ({data['ip_address']}): {e}"
            )

    logging.info(
        (
            "Seed finalizado. Novos ativos criados: %d. Ativos atualizados: %d. "
            "Vendors vinculados (novos): %d. Vendors vinculados (existentes): %d."
        )
        % (created_count, updated_count, vendor_linked_new, vendor_linked_existing)
    )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_assets()