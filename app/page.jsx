'use client';

import { useState } from 'react';
import { Upload, CheckCircle, AlertTriangle, Package, Send, FileSpreadsheet, RefreshCw, Zap, Database } from 'lucide-react';

export default function Home() {
  const [step, setStep] = useState('upload'); // 'upload', 'review', 'order', 'sent'
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dataSource, setDataSource] = useState('api'); // 'api' or 'csv'
  
  // Data states
  const [posProducts, setPosProducts] = useState([]);
  const [reconciliationData, setReconciliationData] = useState(null);
  const [orderData, setOrderData] = useState(null);
  const [reviewDecisions, setReviewDecisions] = useState({});

  const handleFlowhubSync = async () => {
    if (!location) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/flowhub-inventory?location=${location}&filter=true`);
      const result = await response.json();
      
      if (result.success) {
        setPosProducts(result.data.products);
      } else {
        setError(result.error || 'Failed to fetch from Flowhub');
      }
    } catch (err) {
      setError(`Flowhub API error: ${err.message}. Try CSV upload instead.`);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/upload-csv', {
        method: 'POST',
        body: await file.text(),
        headers: { 'Content-Type': 'text/csv' }
      });
      
      const result = await response.json();
      
      if (result.success) {
        setPosProducts(result.data.products);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReconcile = async () => {
    if (!location || posProducts.length === 0) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/reconcile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pos_products: posProducts,
          location: location
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        setReconciliationData(result.data);
        setStep('review');
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateOrder = async (sendEmail = false) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/generate-orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pos_products: posProducts,
          location: location,
          send_email: sendEmail
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        setOrderData(result.data);
        setStep(sendEmail ? 'sent' : 'order');
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewDecision = (index, decision) => {
    setReviewDecisions(prev => ({ ...prev, [index]: decision }));
  };

  const allReviewsComplete = reconciliationData?.needs_review?.length === 0 || 
    Object.keys(reviewDecisions).length === reconciliationData?.needs_review?.length;

  // ============================================================
  // UPLOAD STEP
  // ============================================================
  if (step === 'upload') {
    return (
      <main className="min-h-screen bg-gray-100 p-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">🌿 Black Tie Orders</h1>
          <p className="text-gray-600 mb-8">Production Order System</p>
          
          <div className="bg-white rounded-lg shadow-sm p-6 space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
                {error}
              </div>
            )}
            
            <div>
              <label className="block text-sm font-medium mb-2">Select Location</label>
              <select 
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className="w-full border rounded-lg p-3"
              >
                <option value="">Choose location...</option>
                <option value="lewiston">Lewiston</option>
                <option value="greene">Greene</option>
              </select>
            </div>

            {/* Data Source Toggle */}
            <div className="flex gap-2 p-1 bg-gray-100 rounded-lg">
              <button
                onClick={() => setDataSource('api')}
                className={`flex-1 py-2 px-4 rounded-md flex items-center justify-center gap-2 transition-colors ${
                  dataSource === 'api' 
                    ? 'bg-white shadow text-blue-600' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Zap className="w-4 h-4" />
                Flowhub API
              </button>
              <button
                onClick={() => setDataSource('csv')}
                className={`flex-1 py-2 px-4 rounded-md flex items-center justify-center gap-2 transition-colors ${
                  dataSource === 'csv' 
                    ? 'bg-white shadow text-blue-600' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Upload className="w-4 h-4" />
                CSV Upload
              </button>
            </div>

            {/* Flowhub API Option */}
            {dataSource === 'api' && (
              <div className="border-2 border-blue-200 rounded-lg p-6 bg-blue-50/50">
                <div className="flex items-center gap-3 mb-4">
                  <Database className="w-6 h-6 text-blue-600" />
                  <div>
                    <div className="font-medium">Pull from Flowhub</div>
                    <div className="text-sm text-gray-600">Real-time inventory, no export needed</div>
                  </div>
                </div>
                <button
                  onClick={handleFlowhubSync}
                  disabled={!location || loading}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <Zap className="w-5 h-5" />
                      Sync from Flowhub
                    </>
                  )}
                </button>
              </div>
            )}

            {/* CSV Upload Option */}
            {dataSource === 'csv' && (
              <div>
                <label className="block text-sm font-medium mb-2">Upload Flowhub CSV</label>
                <label className="border-2 border-dashed rounded-lg p-8 text-center hover:border-blue-400 hover:bg-blue-50/50 transition-colors cursor-pointer block">
                  <input 
                    type="file" 
                    accept=".csv" 
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                  <div className="text-sm text-gray-600">
                    {loading ? 'Processing...' : 'Drop CSV file here or click to browse'}
                  </div>
                </label>
              </div>
            )}

            {posProducts.length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">{posProducts.length} Black Tie products loaded</span>
                </div>
              </div>
            )}

            <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg">
              <FileSpreadsheet className="w-5 h-5 text-blue-600" />
              <div>
                <div className="text-sm font-medium text-blue-800">Production Sheet</div>
                <div className="text-xs text-blue-600">Will be loaded automatically from Google Sheets</div>
              </div>
            </div>

            <button
              onClick={handleReconcile}
              disabled={!location || posProducts.length === 0 || loading}
              className="w-full bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {loading && <RefreshCw className="w-5 h-5 animate-spin" />}
              Run Reconciliation
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ============================================================
  // REVIEW STEP
  // ============================================================
  if (step === 'review') {
    const { summary, auto_matched, needs_review, unmatched, production_only } = reconciliationData;
    
    return (
      <main className="min-h-screen bg-gray-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">Inventory Reconciliation</h1>
              <p className="text-gray-600">{location.charAt(0).toUpperCase() + location.slice(1)} • {new Date().toLocaleDateString()}</p>
            </div>
            <button
              onClick={() => setStep('upload')}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Start Over
            </button>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg border-l-4 border-green-500 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <div>
                  <div className="text-2xl font-bold">{summary.auto_matched}</div>
                  <div className="text-sm text-gray-600">Auto-Matched</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg border-l-4 border-amber-500 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                <div>
                  <div className="text-2xl font-bold">{summary.needs_review}</div>
                  <div className="text-sm text-gray-600">Needs Review</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg border-l-4 border-red-500 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <div>
                  <div className="text-2xl font-bold">{summary.unmatched}</div>
                  <div className="text-sm text-gray-600">Unmatched</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg border-l-4 border-blue-500 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <Package className="w-5 h-5 text-blue-600" />
                <div>
                  <div className="text-2xl font-bold">{summary.production_only}</div>
                  <div className="text-sm text-gray-600">Production Only</div>
                </div>
              </div>
            </div>
          </div>

          {/* Needs Review Section */}
          {needs_review.length > 0 && (
            <div className="bg-white rounded-lg border border-amber-200 mb-6">
              <div className="bg-amber-50 p-4 border-b border-amber-200">
                <h3 className="font-medium text-amber-800 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5" />
                  Needs Review ({needs_review.length})
                </h3>
              </div>
              <div className="p-4 space-y-3">
                {needs_review.map((item, idx) => (
                  <div key={idx} className={`border rounded-lg p-4 ${
                    reviewDecisions[idx] ? 'bg-gray-50' : 'bg-amber-50/30 border-amber-300'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{item.pos_name}</div>
                        <div className="text-sm text-gray-500">{item.pos_type}</div>
                      </div>
                      <div className="text-center px-4">
                        <div className="text-amber-600 font-medium">{item.similarity_score}%</div>
                        <div className="text-xs text-gray-500">match</div>
                      </div>
                      <div className="text-right">
                        <div className="font-medium">{item.production_name}</div>
                        <div className="text-sm text-gray-500">{item.production_category}</div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <button
                          onClick={() => handleReviewDecision(idx, 'confirm')}
                          className={`px-3 py-1 rounded text-sm ${
                            reviewDecisions[idx] === 'confirm'
                              ? 'bg-green-600 text-white'
                              : 'bg-green-100 text-green-700 hover:bg-green-200'
                          }`}
                        >
                          ✓ Match
                        </button>
                        <button
                          onClick={() => handleReviewDecision(idx, 'reject')}
                          className={`px-3 py-1 rounded text-sm ${
                            reviewDecisions[idx] === 'reject'
                              ? 'bg-red-600 text-white'
                              : 'bg-red-100 text-red-700 hover:bg-red-200'
                          }`}
                        >
                          ✗ Reject
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Production Only Section */}
          {production_only.length > 0 && (
            <div className="bg-white rounded-lg border border-blue-200 mb-6">
              <div className="bg-blue-50 p-4 border-b border-blue-200">
                <h3 className="font-medium text-blue-800 flex items-center gap-2">
                  <Package className="w-5 h-5" />
                  Production Only - Send to Retail ({production_only.length})
                </h3>
              </div>
              <div className="p-4 space-y-2">
                {production_only.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-blue-50/50 rounded">
                    <div>
                      <div className="font-medium">{item.production_name}</div>
                      <div className="text-sm text-gray-500">{item.production_category}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">{item.production_quantity}</div>
                      <div className="text-xs text-gray-500">available</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Continue Button */}
          <div className="flex justify-end gap-4">
            <button
              onClick={() => handleGenerateOrder(false)}
              disabled={loading}
              className="bg-gray-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-gray-700 disabled:bg-gray-300 transition-colors"
            >
              Preview Order
            </button>
            <button
              onClick={() => handleGenerateOrder(true)}
              disabled={loading || !allReviewsComplete}
              className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-300 transition-colors flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
              Generate & Send Order
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ============================================================
  // ORDER PREVIEW / SENT STEP
  // ============================================================
  return (
    <main className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">
              {step === 'sent' ? '✅ Order Sent!' : 'Order Preview'}
            </h1>
            <p className="text-gray-600">{location.charAt(0).toUpperCase() + location.slice(1)}</p>
          </div>
          <button
            onClick={() => {
              setStep('upload');
              setPosProducts([]);
              setReconciliationData(null);
              setOrderData(null);
            }}
            className="text-sm text-blue-600 hover:underline"
          >
            Start New Order
          </button>
        </div>

        {step === 'sent' && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-8 h-8 text-green-600" />
              <div>
                <div className="font-medium text-green-800">Order sent successfully!</div>
                <div className="text-sm text-green-600">
                  Email sent to matt.barlion@gmail.com (CC: blacktiecannabis@gmail.com)
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Order Summary */}
        {orderData && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="font-medium mb-4">Order Summary</h3>
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="text-center p-4 bg-red-50 rounded">
                <div className="text-2xl font-bold text-red-600">{orderData.summary.critical}</div>
                <div className="text-sm text-gray-600">Critical</div>
              </div>
              <div className="text-center p-4 bg-amber-50 rounded">
                <div className="text-2xl font-bold text-amber-600">{orderData.summary.high}</div>
                <div className="text-sm text-gray-600">Low Stock</div>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded">
                <div className="text-2xl font-bold text-blue-600">{orderData.summary.new_products}</div>
                <div className="text-sm text-gray-600">New Products</div>
              </div>
              <div className="text-center p-4 bg-gray-100 rounded">
                <div className="text-2xl font-bold">{orderData.summary.total}</div>
                <div className="text-sm text-gray-600">Total Items</div>
              </div>
            </div>

            {/* Order Items Table */}
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left p-3">Product</th>
                  <th className="text-left p-3">Category</th>
                  <th className="text-right p-3">Current</th>
                  <th className="text-right p-3">Available</th>
                  <th className="text-right p-3">Request</th>
                  <th className="text-center p-3">Priority</th>
                </tr>
              </thead>
              <tbody>
                {orderData.order_items.map((item, idx) => (
                  <tr key={idx} className="border-t">
                    <td className="p-3">{item.product_name}</td>
                    <td className="p-3 text-gray-600">{item.category}</td>
                    <td className="p-3 text-right">{item.pos_quantity}</td>
                    <td className="p-3 text-right">{item.production_available}</td>
                    <td className="p-3 text-right font-medium">{item.requested_quantity}</td>
                    <td className="p-3 text-center">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        item.priority === 'critical' ? 'bg-red-100 text-red-700' :
                        item.priority === 'high' ? 'bg-amber-100 text-amber-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {item.priority}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {step === 'order' && (
              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => handleGenerateOrder(true)}
                  disabled={loading}
                  className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-300 transition-colors flex items-center gap-2"
                >
                  <Send className="w-5 h-5" />
                  Send Order Email
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
