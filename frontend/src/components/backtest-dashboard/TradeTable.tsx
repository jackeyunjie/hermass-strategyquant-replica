import React, { useMemo, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type RowClassParams,
} from 'ag-grid-community';
import { Tag } from 'antd';
import type { Trade } from '../../types';
import { formatCurrency, formatPercentage, formatDate } from '../../utils/formatters';

ModuleRegistry.registerModules([AllCommunityModule]);

interface TradeTableProps {
  trades: Trade[];
}

export default function TradeTable({ trades }: TradeTableProps) {
  const [pageSize] = useState(20);

  const columnDefs: ColDef[] = useMemo(() => [
    {
      field: 'trade_id',
      headerName: '交易ID',
      width: 100,
      filter: true,
    },
    {
      field: 'entry_date',
      headerName: '入场日期',
      width: 120,
      filter: 'agDateColumnFilter',
      valueFormatter: (params) => formatDate(params.value as string),
      sortable: true,
    },
    {
      field: 'exit_date',
      headerName: '出场日期',
      width: 120,
      filter: 'agDateColumnFilter',
      valueFormatter: (params) => formatDate(params.value as string),
      sortable: true,
    },
    {
      field: 'direction',
      headerName: '方向',
      width: 80,
      filter: true,
      cellRenderer: (params: { value: string }) => (
        <Tag color={params.value === 'long' ? 'green' : 'red'}>
          {params.value === 'long' ? '多' : '空'}
        </Tag>
      ),
    },
    {
      field: 'entry_price',
      headerName: '入场价',
      width: 100,
      type: 'numericColumn',
      valueFormatter: (params) => `¥${(params.value as number).toFixed(2)}`,
    },
    {
      field: 'exit_price',
      headerName: '出场价',
      width: 100,
      type: 'numericColumn',
      valueFormatter: (params) => `¥${(params.value as number).toFixed(2)}`,
    },
    {
      field: 'pnl',
      headerName: '盈亏',
      width: 120,
      type: 'numericColumn',
      sortable: true,
      valueFormatter: (params) => formatCurrency(params.value as number),
      cellStyle: (params: { value: number }) => ({
        color: params.value >= 0 ? '#52c41a' : '#f5222d',
        fontWeight: 'bold',
      }),
    },
    {
      field: 'pnl_pct',
      headerName: '盈亏%',
      width: 100,
      type: 'numericColumn',
      valueFormatter: (params) => formatPercentage(params.value as number),
      cellStyle: (params: { value: number }) => ({
        color: params.value >= 0 ? '#52c41a' : '#f5222d',
      }),
    },
    {
      field: 'commission',
      headerName: '佣金',
      width: 100,
      type: 'numericColumn',
      valueFormatter: (params) => formatCurrency(params.value as number),
    },
    {
      field: 'reason',
      headerName: '原因',
      width: 120,
      filter: true,
    },
  ], []);

  const defaultColDef = useMemo(() => ({
    resizable: true,
    sortable: true,
  }), []);

  const getRowStyle = (params: RowClassParams) => {
    const pnl = (params.data as Trade).pnl;
    if (pnl > 0) return { background: 'rgba(82, 196, 26, 0.05)' };
    if (pnl < 0) return { background: 'rgba(245, 34, 45, 0.05)' };
    return undefined;
  };

  return (
    <div className="ag-theme-alpine" style={{ height: 400, width: '100%' }}>
      <AgGridReact
        rowData={trades}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        pagination={true}
        paginationPageSize={pageSize}
        paginationPageSizeSelector={[10, 20, 50, 100]}
        getRowStyle={getRowStyle}
        rowSelection="single"
        animateRows={true}
      />
    </div>
  );
}
