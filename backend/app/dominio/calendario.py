def dentro_vinculo(funcionario,data):
    return (funcionario.data_admissao is None or data>=funcionario.data_admissao) and (
        funcionario.data_demissao is None or data<=funcionario.data_demissao)


def motivo_fora_vinculo(funcionario,data):
    return "posterior_demissao" if funcionario.data_demissao and data>funcionario.data_demissao else "anterior_admissao"
