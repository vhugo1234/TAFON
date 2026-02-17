// Minimal example: node export-financials.js
// Install: npm install express exceljs body-parser cors
const express = require('express');
const ExcelJS = require('exceljs');
const bodyParser = require('body-parser');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(bodyParser.json({ limit: '10mb' }));

app.post('/api/v1/financials/export', async (req, res) => {
  try {
    const { event_id, event_name, entries = [], options = {} } = req.body;

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('Relatório Financeiro');

    // Title
    ws.mergeCells('A1:O1');
    const titleCell = ws.getCell('A1');
    titleCell.value = `Relatório Financeiro — Evento: ${event_name || event_id || ''}`;
    titleCell.font = { size: 14, bold: true };

    // Compute total geral
    const totalGeral = entries.reduce((s, e) => s + Number(e.total_line ?? e.total_per_person ?? (e.unit_amount * e.days) || 0), 0);

    // Total geral row
    ws.mergeCells('A2:O2');
    ws.getCell('A2').value = `Total Geral: ${totalGeral.toFixed(2)}`;
    ws.getCell('A2').font = { bold: true };

    // Header row (row 4 after blank)
    ws.addRow([]);
    const headerRow = [
      'Evento','Participante','Função','E-mail','CPF','Telefone',
      'Valor unit. (R$)','Dias trabalhados','Total por pessoa (R$)',
      'PIX','Banco','Agência','Conta','Total da linha (R$)','Observações'
    ];
    ws.addRow(headerRow);
    const header = ws.getRow(4);
    header.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    header.alignment = { horizontal: 'center' };
    header.eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF2E75B6' } };
      cell.border = {
        top: { style: 'thin' }, left: { style: 'thin' }, bottom: { style: 'thin' }, right: { style: 'thin' }
      };
    });

    // Data rows
    for (const e of entries) {
      ws.addRow([
        event_name || '',
        e.participant_name || '',
        e.role || '',
        e.email || '',
        e.cpf || '',
        e.phone || '',
        Number(e.unit_amount || 0),
        Number(e.days || 0),
        Number(e.total_per_person || (e.unit_amount * e.days) || 0),
        e.pix || '',
        e.bank || '',
        e.agency || '',
        e.account || '',
        Number(e.total_line || (e.unit_amount * e.days) || 0),
        e.notes || ''
      ]);
    }

    // bottom total row
    const lastRowIndex = ws.lastRow.number + 1;
    ws.getCell(`N${lastRowIndex}`).value = totalGeral;
    ws.getCell(`N${lastRowIndex}`).numFmt = '"R$"#,##0.00;[Red]-"R$"#,##0.00';
    ws.getCell(`M${lastRowIndex}`).value = 'Total Geral:';
    ws.getCell(`M${lastRowIndex}`).font = { bold: true };
    ws.getCell(`N${lastRowIndex}`).font = { bold: true };

    // column widths
    const widths = [30, 28, 20, 28, 16, 18, 15, 14, 16, 18, 14, 10, 14, 18, 25];
    widths.forEach((w, i) => ws.getColumn(i + 1).width = w);

    // send workbook as response attachment
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="financeiro_${event_id || 'export'}.xlsx"`);

    await wb.xlsx.write(res);
    res.end();
  } catch (err) {
    console.error('export error', err);
    res.status(500).json({ error: 'Erro ao gerar planilha' });
  }
});

if (require.main === module) {
  const port = process.env.PORT || 3001;
  app.listen(port, () => console.log(`Export server listening ${port}`));
}

module.exports = app;
